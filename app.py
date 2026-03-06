
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import yfinance as yf
import random
import os
import sqlite3
import json
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

# ======================
# GLOBAL CONFIG
# ======================
USD_INR = 83.0   # approx USD → INR
DB_PATH = os.path.join(app.instance_path, "users.db")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")


def normalize_env_value(value):
    if value is None:
        return ""
    cleaned = value.strip().strip('"').strip("'")
    return cleaned


def env_to_bool(value, default=False):
    cleaned = normalize_env_value(value).lower()
    if not cleaned:
        return default
    return cleaned in {"1", "true", "yes", "on"}


def env_to_int(value, default):
    cleaned = normalize_env_value(value)
    if not cleaned:
        return default
    try:
        return int(cleaned)
    except ValueError:
        return default


FLASK_SECRET_KEY = normalize_env_value(os.getenv("FLASK_SECRET_KEY")) or "trademind-dev-secret-key-change-me"
FLASK_DEBUG = env_to_bool(os.getenv("FLASK_DEBUG"), default=False)
FLASK_HOST = normalize_env_value(os.getenv("FLASK_HOST")) or "127.0.0.1"
FLASK_PORT = env_to_int(os.getenv("FLASK_PORT"), 5000)

app.secret_key = FLASK_SECRET_KEY

GOOGLE_CLIENT_ID = normalize_env_value(GOOGLE_CLIENT_ID)
GOOGLE_CLIENT_SECRET = normalize_env_value(GOOGLE_CLIENT_SECRET)
GOOGLE_REDIRECT_URI = normalize_env_value(os.getenv("GOOGLE_REDIRECT_URI"))
CHATBOT_API_KEY = normalize_env_value(os.getenv("CHATBOT_API_KEY"))
CHATBOT_API_BASE_URL = normalize_env_value(os.getenv("CHATBOT_API_BASE_URL")) or "https://api.openai.com/v1"
CHATBOT_MODEL = normalize_env_value(os.getenv("CHATBOT_MODEL")) or "gpt-4.1-mini"
CHATBOT_TIMEOUT_SECONDS = env_to_int(os.getenv("CHATBOT_TIMEOUT_SECONDS"), 20)


def is_gemini_key(api_key):
    return bool(api_key) and api_key.startswith("AIza")


def is_openai_style_key(api_key):
    if not api_key:
        return False
    lower = api_key.lower()
    return api_key.startswith("sk-") or "openai" in lower


def detect_chat_provider():
    lower_base = CHATBOT_API_BASE_URL.lower()
    if "generativelanguage.googleapis.com" in lower_base or is_gemini_key(CHATBOT_API_KEY):
        return "gemini"
    return "openai-compatible"


def get_effective_chat_model(provider):
    if provider == "gemini":
        if CHATBOT_MODEL.lower().startswith("gemini"):
            return CHATBOT_MODEL
        return "gemini-1.5-flash"
    return CHATBOT_MODEL


def get_google_redirect_uri():
    return GOOGLE_REDIRECT_URI or url_for("google_callback", _external=True)


def is_google_oauth_configured():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return False
    placeholder_tokens = [
        "your-google-client-id",
        "your-google-client-secret",
        "replace-with",
        "os.getenv("
    ]
    value_blob = f"{GOOGLE_CLIENT_ID} {GOOGLE_CLIENT_SECRET}".lower()
    return not any(token in value_blob for token in placeholder_tokens)


def is_placeholder_google_value(value):
    if not value:
        return False
    return any(token in value.lower() for token in ["your-google", "replace-with", "os.getenv("])


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(app.instance_path, exist_ok=True)
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                email TEXT NOT NULL UNIQUE,
                mobile TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


init_db()


# ======================
# LANDING PAGE
# ======================
@app.route("/")
def landing():
    return render_template("welcome.html")


# ======================
# LOGIN PAGE (CAPTCHA)
# ======================
@app.route("/login", methods=["GET", "POST"])
def login():

    error = None
    info = request.args.get("info")

    # generate captcha
    if "captcha" not in session:
        session["captcha"] = str(random.randint(1000, 9999))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user_captcha = request.form.get("captcha_input")

        if user_captcha != session["captcha"]:
            error = "Captcha incorrect. Please try again."
            session["captcha"] = str(random.randint(1000, 9999))
        elif not email or not password:
            error = "Email and password are required."
            session["captcha"] = str(random.randint(1000, 9999))
        else:
            with get_db_connection() as conn:
                user = conn.execute(
                    "SELECT * FROM users WHERE email = ?",
                    (email,)
                ).fetchone()

            if not user or not check_password_hash(user["password_hash"], password):
                error = "Invalid email or password."
                session["captcha"] = str(random.randint(1000, 9999))
            else:
                session["authenticated"] = True
                session["user_email"] = user["email"]
                session["user_name"] = user["name"]
                session.pop("captcha", None)
                return redirect(url_for("market"))

    return render_template(
        "user_info.html",
        captcha=session["captcha"],
        error=error,
        info=info
    )


@app.route("/register", methods=["GET", "POST"])
def register():

    if session.get("authenticated"):
        return redirect(url_for("market"))

    error = None
    success = None
    form = {
        "name": "",
        "age": "",
        "email": "",
        "mobile": ""
    }

    if request.method == "POST":
        form["name"] = request.form.get("name", "").strip()
        form["age"] = request.form.get("age", "").strip()
        form["email"] = request.form.get("email", "").strip().lower()
        form["mobile"] = request.form.get("mobile", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([form["name"], form["age"], form["email"], form["mobile"], password, confirm_password]):
            error = "Please fill all fields."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            try:
                with get_db_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO users (name, age, email, mobile, password_hash)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            form["name"],
                            int(form["age"]),
                            form["email"],
                            form["mobile"],
                            generate_password_hash(password)
                        )
                    )
                    conn.commit()
                return redirect(url_for("login", info="Registration successful. Please login."))
            except ValueError:
                error = "Age must be a valid number."
            except sqlite3.IntegrityError:
                error = "This email is already registered. One email can have only one account."

    return render_template("register.html", error=error, success=success, form=form)


@app.route("/auth/google")
def google_auth():
    if not is_google_oauth_configured():
        return redirect(url_for("login", info="Google login is not configured yet. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."))

    state = secrets.token_urlsafe(16)
    session["google_oauth_state"] = state

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": get_google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account"
    }
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@app.route("/oauth-health")
def oauth_health():
    redirect_uri = GOOGLE_REDIRECT_URI or "(auto from request host)"
    response = {
        "googleOAuthConfigured": is_google_oauth_configured(),
        "checks": {
            "clientIdPresent": bool(GOOGLE_CLIENT_ID),
            "clientSecretPresent": bool(GOOGLE_CLIENT_SECRET),
            "clientIdLooksPlaceholder": is_placeholder_google_value(GOOGLE_CLIENT_ID),
            "clientSecretLooksPlaceholder": is_placeholder_google_value(GOOGLE_CLIENT_SECRET),
            "redirectUri": redirect_uri,
            "recommendedRedirectUriForLocal": "http://127.0.0.1:5000/auth/google/callback"
        },
        "nextStep": "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env, then restart app." if not is_google_oauth_configured() else "OAuth config detected. If login fails, verify redirect URI and Google Cloud OAuth client settings."
    }
    return jsonify(response)


@app.route("/auth/google/callback")
def google_callback():
    state = request.args.get("state")
    code = request.args.get("code")
    oauth_error = request.args.get("error")

    if oauth_error:
        session.pop("google_oauth_state", None)
        return redirect(url_for("login", info="Google login was cancelled or denied."))

    if not code or not state or state != session.get("google_oauth_state"):
        session.pop("google_oauth_state", None)
        return redirect(url_for("login", info="Google authentication failed. Please try again."))

    if not is_google_oauth_configured():
        session.pop("google_oauth_state", None)
        return redirect(url_for("login", info="Google login is not configured yet. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."))

    token_payload = urlencode({
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": get_google_redirect_uri(),
        "grant_type": "authorization_code"
    }).encode("utf-8")

    try:
        token_request = Request(
            "https://oauth2.googleapis.com/token",
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        token_response = json.loads(urlopen(token_request, timeout=15).read().decode("utf-8"))
        access_token = token_response.get("access_token")
        if not access_token:
            session.pop("google_oauth_state", None)
            return redirect(url_for("login", info="Google authentication failed. Please try again."))

        user_request = Request(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        profile = json.loads(urlopen(user_request, timeout=15).read().decode("utf-8"))
    except Exception:
        session.pop("google_oauth_state", None)
        return redirect(url_for("login", info="Google authentication failed. Please try again."))

    email = (profile.get("email") or "").strip().lower()
    name = (profile.get("name") or "Google User").strip()

    if not email:
        session.pop("google_oauth_state", None)
        return redirect(url_for("login", info="Google account email not available."))

    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            conn.execute(
                """
                INSERT INTO users (name, age, email, mobile, password_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, 18, email, "google-oauth", generate_password_hash(secrets.token_urlsafe(24)))
            )
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

    session["authenticated"] = True
    session["user_email"] = user["email"]
    session["user_name"] = user["name"]
    session.pop("captcha", None)
    session.pop("google_oauth_state", None)
    return redirect(url_for("market"))


# ======================
# HELPER FUNCTIONS
# ======================
def get_index_price(symbol, fallback):
    try:
        data = yf.Ticker(symbol).history(period="1d")
        if data.empty:
            return fallback
        return round(data["Close"].iloc[-1], 2)
    except Exception:
        return fallback


def get_gold_10gm():
    try:
        gold_hist = yf.Ticker("GC=F").history(period="1d")
        if gold_hist.empty:
            return 62000
        gold_usd_oz = gold_hist["Close"].iloc[-1]
        return round((gold_usd_oz * USD_INR / 31.1035) * 10, 2)
    except Exception:
        return 62000


def get_silver_kg():
    try:
        silver_hist = yf.Ticker("SI=F").history(period="1d")
        if silver_hist.empty:
            return 72000
        silver_usd_oz = silver_hist["Close"].iloc[-1]
        return round((silver_usd_oz * USD_INR) / 0.0311035, 2)
    except Exception:
        return 72000


def build_prediction_context(payload):
    if not payload:
        return (
            "No active prediction context available yet. "
            "You can still answer general stock-market and risk-management questions."
        )

    result = payload.get("result", {})
    profile = payload.get("profile", {})

    lines = [
        f"Recommended stock: {result.get('stock', 'N/A')}",
        f"Action: {result.get('action', 'N/A')}",
        f"Present price: {result.get('present', 'N/A')}",
        f"Target price: {result.get('target', 'N/A')}",
        f"Stop-loss: {result.get('stop_loss', 'N/A')}",
        f"Time frame: {result.get('timeframe', 'N/A')}",
        f"Risk appetite: {profile.get('risk', 'N/A')}",
        f"Horizon: {profile.get('horizon', 'N/A')}",
        f"Capital: {profile.get('capital', 'N/A')}",
        f"Sector preference: {profile.get('sector', 'N/A')}",
        f"Market mood: {profile.get('mood', 'N/A')}"
    ]

    explanation = result.get("explanation") or []
    if explanation:
        lines.append("Reasoning points:")
        for item in explanation:
            lines.append(f"- {item}")

    return "\n".join(lines)


def trim_chat_history(history, max_messages=10):
    if not history:
        return []
    cleaned = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            cleaned.append({"role": role, "content": content})
    return cleaned[-max_messages:]


def fallback_chat_response(question, payload, history=None):
    result = (payload or {}).get("result", {})
    profile = (payload or {}).get("profile", {})

    stock = result.get("stock", "the recommended stock")
    action = result.get("action", "HOLD")
    present = result.get("present", "N/A")
    target = result.get("target", "N/A")
    stop_loss = result.get("stop_loss", "N/A")
    timeframe = result.get("timeframe", "the selected horizon")
    risk = profile.get("risk", "your")
    sector = profile.get("sector", "selected")

    q = (question or "").lower()

    if any(k in q for k in ["hello", "hi", "hey", "namaste", "hii", "yo"]):
        return (
            f"Hello! I am your TradeMind assistant. For now, {stock} is marked {action}. "
            "You can ask me why this stock was selected, risk level, target logic, or entry and exit strategy."
        )

    if any(k in q for k in ["thanks", "thank you", "thx"]):
        return "You are welcome. Ask any follow-up and I will break it down in simple terms."

    if any(k in q for k in ["who are you", "what can you do", "help"]):
        return (
            "I am TradeMind assistant. I can explain recommendation reason, risk controls, time horizon fit, "
            "and practical next steps based on your current prediction."
        )

    if any(k in q for k in ["why", "reason", "kyu", "kyun"]):
        return (
            f"{stock} was selected because it matches your {sector} sector preference and {risk} risk profile. "
            f"For {timeframe}, the engine suggests {action} with target near {target} and risk control at {stop_loss}."
        )

    if any(k in q for k in ["target", "return", "upside"]):
        return (
            f"Current price reference is {present} and model target is {target} for {timeframe}. "
            "Treat this as scenario guidance, not guaranteed return."
        )

    if any(k in q for k in ["risk", "stop", "loss", "safe"]):
        return (
            f"Risk control is set with stop-loss at {stop_loss}. If price breaks this zone, capital protection is prioritized. "
            f"Given your {risk} risk profile, position sizing should stay conservative."
        )

    return (
        f"Summary: {stock} is currently marked {action} with present {present}, target {target}, and stop-loss {stop_loss} "
        f"for {timeframe}. Ask about risk, target logic, entry strategy, or sector outlook for deeper detail."
    )


def ask_prediction_chatbot(question, payload, history=None):
    if not CHATBOT_API_KEY:
        return fallback_chat_response(question, payload, history=history), "fallback"

    context = build_prediction_context(payload)
    recent_history = trim_chat_history(history)
    provider = detect_chat_provider()
    model_name = get_effective_chat_model(provider)

    system_prompt = (
        "You are TradeMind AI assistant. Be conversational like a real chat assistant. "
        "If user greets, greet naturally. Explain stock recommendations simply and clearly. "
        "Never guarantee profits. Keep replies practical and user-friendly."
    )

    try:
        if provider == "gemini":
            endpoint = (
                f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                f"?key={CHATBOT_API_KEY}"
            )

            contents = []
            for item in recent_history:
                role = "model" if item.get("role") == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": item.get("content", "")}]} )

            user_text = f"Prediction context:\n{context}\n\nUser question: {question}"
            contents.append({"role": "user", "parts": [{"text": user_text}]})

            body = {
                "systemInstruction": {
                    "parts": [{"text": system_prompt}]
                },
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 600
                }
            }

            req = Request(
                endpoint,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            raw = urlopen(req, timeout=CHATBOT_TIMEOUT_SECONDS).read().decode("utf-8")
            parsed = json.loads(raw)
            parts = (
                parsed.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [])
            )
            answer = "\n".join((p.get("text", "") or "").strip() for p in parts if p.get("text"))
            answer = answer.strip()
            if not answer:
                return fallback_chat_response(question, payload, history=history), "fallback"
            return answer, "api"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"Prediction context:\n{context}"}
        ]
        messages.extend(recent_history)
        messages.append({"role": "user", "content": question})

        body = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.4
        }
        endpoint = f"{CHATBOT_API_BASE_URL.rstrip('/')}/chat/completions"

        req = Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {CHATBOT_API_KEY}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        raw = urlopen(req, timeout=CHATBOT_TIMEOUT_SECONDS).read().decode("utf-8")
        parsed = json.loads(raw)
        answer = (
            parsed.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not answer:
            return fallback_chat_response(question, payload, history=history), "fallback"
        return answer, "api"
    except Exception:
        return fallback_chat_response(question, payload, history=history), "fallback"


# ======================
# MARKET DASHBOARD (PROTECTED)
# ======================
@app.route("/market")
def market():

    if not session.get("authenticated"):
        return redirect("/login")

    nifty_price = get_index_price("^NSEI", 22450)
    sensex_price = get_index_price("^BSESN", 74000)
    banknifty_price = get_index_price("^NSEBANK", 47800)

    gold_price = get_gold_10gm()
    silver_price = get_silver_kg()

    try:
        df_dates = yf.download("^NSEI", period="5d", interval="1d", progress=False)
        if df_dates.empty:
            dates = ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5"]
        else:
            dates = df_dates.index.strftime("%Y-%m-%d").tolist()
    except Exception:
        dates = ["Day 1","Day 2","Day 3","Day 4","Day 5"]

    nifty = [nifty_price - 200, nifty_price - 120, nifty_price - 60, nifty_price - 30, nifty_price]
    sensex = [sensex_price - 500, sensex_price - 300, sensex_price - 200, sensex_price - 100, sensex_price]
    banknifty = [banknifty_price - 600, banknifty_price - 350, banknifty_price - 200, banknifty_price - 100, banknifty_price]

    gold = [gold_price - 800, gold_price - 500, gold_price - 300, gold_price - 100, gold_price]
    silver = [silver_price - 2000, silver_price - 1200, silver_price - 600, silver_price - 300, silver_price]

    stock_names = ["RELIANCE","TCS","INFY","HDFCBANK","ICICI","SBIN","ITC","LT"]
    stock_prices = [2900,3850,1620,1500,1100,720,450,3400]

    return render_template(
        "market.html",
        dates=dates,
        nifty=nifty,
        sensex=sensex,
        banknifty=banknifty,
        gold=gold,
        silver=silver,
        stock_names=stock_names,
        stock_prices=stock_prices,
        nifty_kpi=nifty_price,
        sensex_kpi=sensex_price,
        banknifty_kpi=banknifty_price,
        gold_kpi=gold_price,
        silver_kpi=silver_price,
    )


# ======================
# STOCK PREDICTION (PROTECTED)
# ======================
@app.route("/predict", methods=["GET", "POST"])
def predict():

    if not session.get("authenticated"):
        return redirect("/login")

    result = None

    form = {
        "risk": "",
        "horizon": "",
        "capital": "",
        "sector": "",
        "mood": "",
        "timeframe": ""
    }

    symbols = {
        "HDFCBANK": "HDFCBANK.NS",
        "ICICIBANK": "ICICIBANK.NS",
        "TCS": "TCS.NS",
        "INFY": "INFY.NS",
        "ITC": "ITC.NS",
        "SBIN": "SBIN.NS",
        "RELIANCE": "RELIANCE.NS",
        "LT": "LT.NS",
        "TATAMOTORS": "TATAMOTORS.NS"
    }

    fallback_prices = {
        "HDFCBANK": 1500,
        "ICICIBANK": 1100,
        "TCS": 3850,
        "INFY": 1620,
        "ITC": 450,
        "SBIN": 720,
        "RELIANCE": 2900,
        "LT": 3400,
        "TATAMOTORS": 980
    }

    if request.method == "POST":

        for k in form:
            form[k] = request.form.get(k, "")

        sector_map = {
            "Banking": ["HDFCBANK", "ICICIBANK", "SBIN"],
            "IT": ["TCS", "INFY"],
            "Auto": ["TATAMOTORS"],
            "FMCG": ["ITC"]
        }

        candidates = sector_map.get(form["sector"], ["ITC"])
        stock = candidates[hash(form["risk"] + form["horizon"]) % len(candidates)]

        ticker = yf.Ticker(symbols.get(stock, "ITC.NS"))
        try:
            hist = ticker.history(period="1mo")
            if hist.empty:
                present = fallback_prices.get(stock, 450)
            else:
                present = round(hist["Close"].iloc[-1], 2)
        except Exception:
            present = fallback_prices.get(stock, 450)

        if form["timeframe"] == "1M":
            target = round(present * 1.06, 2)
            tf = "1 Month"
        elif form["timeframe"] == "3M":
            target = round(present * 1.12, 2)
            tf = "3 Months"
        else:
            target = round(present * 1.25, 2)
            tf = "6–12 Months"

        stop_loss = round(present * 0.95, 2)

        explanation = [
            f"{stock} belongs to the {form['sector']} sector",
            "Historical data shows stable movement",
            f"Risk level ({form['risk']}) aligns with volatility",
            f"Target price derived for {tf}",
            "Stop-loss added for downside protection"
        ]

        result = {
            "stock": stock,
            "action": "BUY" if form["risk"] != "Low" else "HOLD",
            "present": present,
            "target": target,
            "stop_loss": stop_loss,
            "timeframe": tf,
            "explanation": explanation
        }

        session["latest_prediction"] = {
            "result": result,
            "profile": dict(form)
        }
        session["prediction_chat_history"] = []

    return render_template("predict.html", result=result, form=form)


@app.route("/predict/chatbot", methods=["POST"])
def predict_chatbot():

    if not session.get("authenticated"):
        return jsonify({"error": "Unauthorized"}), 401

    payload = session.get("latest_prediction", {})

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"error": "Message is required."}), 400

    history = trim_chat_history(session.get("prediction_chat_history", []))
    reply, source = ask_prediction_chatbot(message, payload, history=history)

    updated_history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply}
    ]
    session["prediction_chat_history"] = trim_chat_history(updated_history)

    return jsonify({"reply": reply, "source": source})


# ======================
# LOGOUT
# ======================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ======================
# RUN APP
# ======================
if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)

