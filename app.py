##from flask import Flask, render_template, request, redirect, session
##import yfinance as yf
##import random
##import sqlite3
##from werkzeug.security import generate_password_hash, check_password_hash
##import csv
##
##app = Flask(__name__)
##app.secret_key = "trademind-secret-key"
##
##USD_INR = 83.0
##
##
### ======================
### DATABASE INIT
### ======================
##def init_db():
##    conn = sqlite3.connect("trademind.db")
##    c = conn.cursor()
##
##    c.execute("""
##        CREATE TABLE IF NOT EXISTS users (
##            id INTEGER PRIMARY KEY AUTOINCREMENT,
##            fullname TEXT NOT NULL,
##            username TEXT UNIQUE NOT NULL,
##            email TEXT UNIQUE NOT NULL,
##            password TEXT NOT NULL,
##            risk_profile TEXT NOT NULL
##        )
##    """)

##    c.execute("""
##        CREATE TABLE IF NOT EXISTS prediction_history (
##            id INTEGER PRIMARY KEY AUTOINCREMENT,
##            username TEXT,
##            stock TEXT,
##            sector TEXT,
##            action TEXT,
##            present REAL,
##            target REAL,
##            stop_loss REAL,
##            timeframe TEXT,
##            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
##        )
##    """)
##
##    conn.commit()
##    conn.close()
##
##init_db()
##
##
### ======================
### HELPER FUNCTIONS
### ======================
##def get_index_price(symbol, fallback):
##    try:
##        data = yf.Ticker(symbol).history(period="1d")
##        if data.empty:
##            return fallback
##        return round(data["Close"].iloc[-1], 2)
##    except:
##        return fallback
##
##
##def get_gold_10gm():
##    try:
##        gold_usd_oz = yf.Ticker("GC=F").history(period="1d")["Close"].iloc[-1]
##        return round((gold_usd_oz * USD_INR / 31.1035) * 10, 2)
##    except:
##        return 62000
##
##
##def get_silver_kg():
##    try:
##        silver_usd_oz = yf.Ticker("SI=F").history(period="1d")["Close"].iloc[-1]
##        return round((silver_usd_oz * USD_INR) / 0.0311035, 2)
##    except:
##        return 72000
##
##
### ======================
### LANDING
### ======================
##@app.route("/")
##def landing():
##    # Fetch live market data for landing page
##    nifty_price = get_index_price("^NSEI", 22450)
##    sensex_price = get_index_price("^BSESN", 74000)
##    banknifty_price = get_index_price("^NSEBANK", 47800)
##    
##    gold_price = get_gold_10gm()
##    silver_price = get_silver_kg()
##    
##    try:
##        df_dates = yf.download("^NSEI", period="5d", interval="1d", progress=False)
##        dates = df_dates.index.strftime("%a, %b %d").tolist()
##        nifty_data = df_dates["Close"].round(2).tolist()
##    except:
##        dates = ["Day 1","Day 2","Day 3","Day 4","Day 5"]
##        nifty_data = [nifty_price - 200, nifty_price - 120, nifty_price - 60, nifty_price - 30, nifty_price]
##    
##    return render_template(
##        "welcome.html",
##        nifty_price=nifty_price,
##        sensex_price=sensex_price,
##        banknifty_price=banknifty_price,
##        gold_price=gold_price,
##        silver_price=silver_price,
##        dates=dates,
##        nifty_data=nifty_data
##    )
##
##
### ======================
### SIGNUP
### ======================
##@app.route("/signup", methods=["GET", "POST"])
##def signup():
##
##    error = None
##
##    if request.method == "POST":
##
##        fullname = request.form["fullname"]
##        username = request.form["username"]
##        email = request.form["email"]
##        password = request.form["password"]
##        confirm = request.form["confirm_password"]
##        risk = request.form["risk"]
##
##        if password != confirm:
##            error = "Passwords do not match ❌"
##            return render_template("signup.html", error=error)
##
##        hashed_password = generate_password_hash(password)
##
##        try:
##            conn = sqlite3.connect("trademind.db")
##            c = conn.cursor()
##
##            c.execute("""
##                INSERT INTO users (fullname, username, email, password, risk_profile)
##                VALUES (?, ?, ?, ?, ?)
##            """, (fullname, username, email, hashed_password, risk))
##
##            conn.commit()
##            conn.close()
##
##            return redirect("/login")
##
##        except sqlite3.IntegrityError:
##            error = "Username or Email already exists ❌"
##
##    return render_template("signup.html", error=error)
##
##
### ======================
### LOGIN
### ======================
##@app.route("/login", methods=["GET", "POST"])
##def login():
##
##    error = None
##
##    if "captcha" not in session:
##        session["captcha"] = str(random.randint(1000, 9999))
##
##    if request.method == "POST":
##
##        username = request.form.get("username")
##        password = request.form.get("password")
##        user_captcha = request.form.get("captcha_input")
##
##        if user_captcha != session["captcha"]:
##            error = "Captcha incorrect ❌"
##            session["captcha"] = str(random.randint(1000, 9999))
##
##        else:
##            conn = sqlite3.connect("trademind.db")
##            c = conn.cursor()
##            c.execute("SELECT * FROM users WHERE username=?", (username,))
##            user = c.fetchone()
##            conn.close()
##
##            if user and check_password_hash(user[4], password):
##                session["authenticated"] = True
##                session["user"] = username
##                session.pop("captcha", None)
##                return redirect("/market")
##            else:
##                error = "Invalid username or password ❌"
##
##    return render_template(
##        "user_info.html",
##        captcha=session["captcha"],
##        error=error
##    )
##
##
### ======================
### MARKET DASHBOARD
### ======================
##@app.route("/market")
##def market():
##
##    if not session.get("authenticated"):
##        return redirect("/login")
##
##    try:
##        df = yf.download("^NSEI", period="5d", interval="1d")
##        dates = df.index.strftime("%Y-%m-%d").tolist()
##        nifty = df["Close"].round(2).tolist()
##        nifty_kpi = nifty[-1]
##    except:
##        dates = ["D1","D2","D3","D4","D5"]
##        nifty = [22400,22450,22500,22600,22700]
##        nifty_kpi = nifty[-1]
##
##    try:
##        sensex = yf.download("^BSESN", period="5d")["Close"].round(2).tolist()
##        sensex_kpi = sensex[-1]
##    except:
##        sensex = [73000,73200,73400,73500,73600]
##        sensex_kpi = sensex[-1]
##
##    try:
##        banknifty = yf.download("^NSEBANK", period="5d")["Close"].round(2).tolist()
##        banknifty_kpi = banknifty[-1]
##    except:
##        banknifty = [47000,47200,47400,47500,47600]
##        banknifty_kpi = banknifty[-1]
##
##    # GOLD
##    try:
##        gold_usd = yf.Ticker("GC=F").history(period="1d")["Close"].iloc[-1]
##        gold_kpi = round((gold_usd * USD_INR / 31.1035) * 10, 2)
##        gold = [gold_kpi*0.97, gold_kpi*0.98, gold_kpi*0.99, gold_kpi*1.01, gold_kpi]
##    except:
##        gold_kpi = 62000
##        gold = [61000,61500,61800,62000,62200]
##
##    # SILVER
##    try:
##        silver_usd = yf.Ticker("SI=F").history(period="1d")["Close"].iloc[-1]
##        silver_kpi = round((silver_usd * USD_INR) / 0.0311035, 2)
##        silver = [silver_kpi*0.97, silver_kpi*0.98, silver_kpi*0.99, silver_kpi*1.01, silver_kpi]
##    except:
##        silver_kpi = 72000
##        silver = [71000,71500,71800,72000,72200]
##
##    stock_names = ["RELIANCE","TCS","INFY","HDFCBANK","ICICI"]
##    stock_prices = [2900,3850,1620,1500,1100]
##
##
##    conn = sqlite3.connect("trademind.db")
##    c = conn.cursor() 
##    c.execute("""
##    SELECT stock, action, present, target, stop_loss, timeframe, created_at
##    FROM prediction_history
##    WHERE username=?
##    ORDER BY created_at DESC
##    LIMIT 10
##    """,(session["user"],))
##    
##    history = c.fetchall()
##    
##    conn.close()
##
##    return render_template(
##    "market.html",
##    dates=dates,
##    nifty=nifty,
##    sensex=sensex,
##    banknifty=banknifty,
##    gold=gold,
##    silver=silver,
##    stock_names=stock_names,
##    stock_prices=stock_prices,
##    nifty_kpi=nifty_kpi,
##    sensex_kpi=sensex_kpi,
##    banknifty_kpi=banknifty_kpi,
##    gold_kpi=gold_kpi,
##    silver_kpi=silver_kpi,
##    history=history
##    )
##
##
### ======================
### PREDICTION
### ======================
##@app.route("/predict", methods=["GET", "POST"])
##def predict():
##
##    if not session.get("authenticated"):
##        return redirect("/login")
##
##    result = None
##    error = None
##
##    form = {
##        "risk": "",
##        "horizon": "",
##        "capital": "",
##        "sector": "",
##        "mood": "",
##        "timeframe": ""
##    }
##
##    if request.method == "POST":
##
##        for key in form:
##            form[key] = request.form.get(key)
##
##        stocks_by_sector = {}
##
##        with open("stocks.csv", newline='') as csvfile:
##            reader = csv.DictReader(csvfile)
##            for row in reader:
##                sector = row["sector"].strip()
##                symbol = row["symbol"].strip()
##
##                stocks_by_sector.setdefault(sector, []).append(symbol)
##
##        selected_sector = form["sector"]
##
##        if selected_sector not in stocks_by_sector:
##            error = "No stocks found for selected sector ❌"
##            return render_template("predict.html", result=result, form=form, error=error)
##
##        stock = random.choice(stocks_by_sector[selected_sector])
##
##        ticker_symbol = stock + ".NS"
##
##        try:
##            ticker = yf.Ticker(ticker_symbol)
##            hist = ticker.history(period="5d")
##            present = round(hist["Close"].iloc[-1], 2)
##        except:
##            present = 500
##
##        if form["timeframe"] == "1M":
##            target = round(present * 1.05, 2)
##        elif form["timeframe"] == "3M":
##            target = round(present * 1.12, 2)
##        else:
##            target = round(present * 1.20, 2)
##
##        stop_loss = round(present * 0.95, 2)
##
##        action = "BUY" if form["risk"] == "High" else "HOLD"
##
##        result = {
##            "stock": stock,
##            "sector": selected_sector,
##            "action": action,
##            "present": present,
##            "target": target,
##            "stop_loss": stop_loss,
##            "timeframe": form["timeframe"]
##        }
##
##        # Save prediction to history
##        conn = sqlite3.connect("trademind.db")
##        c = conn.cursor()
##        c.execute("""
##        INSERT INTO prediction_history
##        (username, stock, sector, action, present, target, stop_loss, timeframe)
##        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
##        """,(
##        session["user"],
##        stock,
##        selected_sector,
##        action,
##        present,
##        target,
##        stop_loss,
##        form["timeframe"]
##        ))
##        
##        conn.commit()
##        conn.close()
##        
##    return render_template("predict.html", result=result, form=form, error=error)
##
##
### ======================
### LOGOUT
### ======================
##@app.route("/logout")
##def logout():
##    session.clear()
##    return redirect("/")
##
##
### ======================
### RUN
### ======================
##if __name__ == "__main__":
##    app.run(debug=True)##



from flask import Flask, render_template, request, redirect, session
import yfinance as yf
import random
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import csv


app = Flask(__name__)
app.secret_key = "trademind-secret-key"

USD_INR = 83.0

# ======================
# DATABASE INIT
# ======================
def init_db():
    conn = sqlite3.connect("trademind.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password TEXT,
            risk_profile TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS prediction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            stock TEXT,
            sector TEXT,
            action TEXT,
            present REAL,
            target REAL,
            stop_loss REAL,
            timeframe TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

init_db()


# ======================
# HELPER FUNCTIONS
# ======================

def get_stock_price(symbol, fallback=None):
    try:
        data = yf.Ticker(symbol).history(period="1d")

        if data.empty:
            return fallback

        return round(data["Close"].iloc[-1], 2)

    except:
        return fallback


# 🟡 INDICES → Yahoo
def get_index_price(symbol, fallback):
    try:
        data = yf.Ticker(symbol).history(period="1d")
        if data.empty:
            return fallback
        return round(data["Close"].iloc[-1], 2)
    except:
        return fallback


# 🟡 5-Day Chart → Yahoo
def get_5day_series(symbol, fallback_prices):
    try:
        df = yf.download(symbol, period="5d", interval="1d", progress=False)
        if df.empty:
            return ["D1","D2","D3","D4","D5"], fallback_prices

        dates = df.index.strftime("%a").tolist()
        prices = df["Close"].round(2).tolist()

        return dates, prices
    except:
        return ["D1","D2","D3","D4","D5"], fallback_prices


# GOLD / SILVER
def get_gold_10gm():
    try:
        gold = yf.Ticker("GC=F").history(period="1d")["Close"].iloc[-1]
        return round((gold * USD_INR / 31.1035) * 10, 2)
    except:
        return 62000


def get_silver_kg():
    try:
        silver = yf.Ticker("SI=F").history(period="1d")["Close"].iloc[-1]
        return round((silver * USD_INR) / 0.0311035, 2)
    except:
        return 72000


# ======================
# ROUTES
# ======================

@app.route("/")
def landing():
    nifty_price = get_index_price("^NSEI", 22450)
    sensex_price = get_index_price("^BSESN", 74000)
    banknifty_price = get_index_price("^NSEBANK", 47800)

    gold_price = get_gold_10gm()
    silver_price = get_silver_kg()

    dates, nifty_data = get_5day_series("^NSEI", [22400,22450,22500,22600,22700])

    return render_template(
        "welcome.html",
        nifty_price=nifty_price,
        sensex_price=sensex_price,
        banknifty_price=banknifty_price,
        gold_price=gold_price,
        silver_price=silver_price,
        dates=dates,
        nifty_data=nifty_data
    )


@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None

    if request.method == "POST":
        fullname = request.form["fullname"]
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm = request.form["confirm_password"]
        risk = request.form["risk"]

        if password != confirm:
            return render_template("signup.html", error="Passwords do not match ❌")

        hashed_password = generate_password_hash(password)

        try:
            conn = sqlite3.connect("trademind.db")
            c = conn.cursor()

            c.execute("""
                INSERT INTO users (fullname, username, email, password, risk_profile)
                VALUES (?, ?, ?, ?, ?)
            """, (fullname, username, email, hashed_password, risk))

            conn.commit()
            conn.close()

            return redirect("/login")

        except sqlite3.IntegrityError:
            error = "Username or Email already exists ❌"

    return render_template("signup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if "captcha" not in session:
        session["captcha"] = str(random.randint(1000, 9999))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user_captcha = request.form.get("captcha_input")

        if user_captcha != session["captcha"]:
            error = "Captcha incorrect ❌"
        else:
            conn = sqlite3.connect("trademind.db")
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=?", (username,))
            user = c.fetchone()
            conn.close()

            if user and check_password_hash(user[4], password):
                session["authenticated"] = True
                session["user"] = username
                session.pop("captcha", None)
                return redirect("/market")
            else:
                error = "Invalid credentials ❌"

    return render_template("user_info.html", captcha=session["captcha"], error=error)


@app.route("/market")
def market():

    if not session.get("authenticated"):
        return redirect("/login")

    dates, nifty = get_5day_series("^NSEI", [22400,22450,22500,22600,22700])
    nifty_kpi = nifty[-1] if nifty else 22450

    _, sensex = get_5day_series("^BSESN", [73000,73200,73400,73500,73600])
    sensex_kpi = sensex[-1] if sensex else 74000

    _, banknifty = get_5day_series("^NSEBANK", [47000,47200,47400,47500,47600])
    banknifty_kpi = banknifty[-1] if banknifty else 47800

    gold_kpi = get_gold_10gm()
    gold = [gold_kpi*0.97, gold_kpi*0.98, gold_kpi*0.99, gold_kpi*1.01, gold_kpi]

    silver_kpi = get_silver_kg()
    silver = [silver_kpi*0.97, silver_kpi*0.98, silver_kpi*0.99, silver_kpi*1.01, silver_kpi]

    stock_names = ["AAPL","MSFT","GOOGL","AMZN","TSLA"]
    stock_prices = [get_stock_price(s) for s in stock_names]

    conn = sqlite3.connect("trademind.db")
    c = conn.cursor()
    c.execute("""
    SELECT stock, action, present, target, stop_loss, timeframe, created_at
    FROM prediction_history
    WHERE username=?
    ORDER BY created_at DESC
    LIMIT 10
    """,(session["user"],))
    
    history = c.fetchall()
    conn.close()

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
        nifty_kpi=nifty_kpi,
        sensex_kpi=sensex_kpi,
        banknifty_kpi=banknifty_kpi,
        gold_kpi=gold_kpi,
        silver_kpi=silver_kpi,
        history=history
    )


@app.route("/predict", methods=["GET", "POST"])
def predict():

    if not session.get("authenticated"):
        return redirect("/login")

    result = None
    error = None

    form = {
        "risk": "",
        "horizon": "",
        "capital": "",
        "sector": "",
        "mood": "",
        "timeframe": ""
    }

    if request.method == "POST":
        print("METHOD:", request.method)

        for key in form:
            form[key] = request.form.get(key)

        stocks_by_sector = {}

        with open("stocks.csv", newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                stocks_by_sector.setdefault(row["sector"], []).append(row["symbol"])

        sector = form["sector"]

        if sector not in stocks_by_sector:
            return render_template("predict.html", error="No stocks found ❌", form=form)

        stock = random.choice(stocks_by_sector[sector])

        present = get_stock_price(stock)

        # 🔥 VERY IMPORTANT CHECK
        if present is None:
            return render_template("predict.html", error="Stock data not available ❌", form=form)

        # 🔥 OPTION 1 (simple logic - current)
        # target = round(present * (1.05 if form["timeframe"]=="1M" else 1.12 if form["timeframe"]=="3M" else 1.2),2)
        # stop_loss = round(present * 0.95,2)

        # 🔥 OPTION 2 (BETTER - random realistic)
        change = random.uniform(1.03, 1.15)
        target = round(present * change, 2)

        stop_loss = round(present * random.uniform(0.90, 0.97), 2)

        action = "BUY" if form["risk"] == "High" else "HOLD"

        result = {
            "stock": stock,
            "sector": sector,
            "action": action,
            "present": present,
            "target": target,
            "stop_loss": stop_loss,
            "timeframe": form["timeframe"]
        }

        conn = sqlite3.connect("trademind.db")
        c = conn.cursor()
        c.execute("""
        INSERT INTO prediction_history
        (username, stock, sector, action, present, target, stop_loss, timeframe)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,(session["user"], stock, sector, action, present, target, stop_loss, form["timeframe"]))
        
        conn.commit()
        conn.close()

    return render_template("predict.html", result=result, form=form, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)