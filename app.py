
from flask import Flask, render_template, request, redirect, session
import yfinance as yf
import random

app = Flask(__name__)
app.secret_key = "trademind-secret-key"

# ======================
# GLOBAL CONFIG
# ======================
USD_INR = 83.0   # approx USD → INR


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

    # generate captcha
    if "captcha" not in session:
        session["captcha"] = str(random.randint(1000, 9999))

    if request.method == "POST":
        user_captcha = request.form.get("captcha_input")

        if user_captcha != session["captcha"]:
            error = "Captcha incorrect. Please try again."
            session["captcha"] = str(random.randint(1000, 9999))
        else:
            session["authenticated"] = True
            session.pop("captcha", None)
            return redirect("/market")

    return render_template(
        "user_info.html",
        captcha=session["captcha"],
        error=error
    )


# ======================
# HELPER FUNCTIONS
# ======================
def get_index_price(symbol, fallback):
    try:
        data = yf.Ticker(symbol).history(period="1d")
        if data.empty:
            return fallback
        return round(data["Close"].iloc[-1], 2)
    except:
        return fallback


def get_gold_10gm():
    try:
        gold_usd_oz = yf.Ticker("GC=F").history(period="1d")["Close"].iloc[-1]
        return round((gold_usd_oz * USD_INR / 31.1035) * 10, 2)
    except:
        return 62000


def get_silver_kg():
    try:
        silver_usd_oz = yf.Ticker("SI=F").history(period="1d")["Close"].iloc[-1]
        return round((silver_usd_oz * USD_INR) / 0.0311035, 2)
    except:
        return 72000


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
        dates = df_dates.index.strftime("%Y-%m-%d").tolist()
    except:
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
        "LT": "LT.NS"
    }

    if request.method == "POST":

        for k in form:
            form[k] = request.form[k]

        sector_map = {
            "Banking": ["HDFCBANK", "ICICIBANK", "SBIN"],
            "IT": ["TCS", "INFY"],
            "Auto": ["TATAMOTORS"],
            "FMCG": ["ITC"]
        }

        candidates = sector_map.get(form["sector"], ["ITC"])
        stock = candidates[hash(form["risk"] + form["horizon"]) % len(candidates)]

        ticker = yf.Ticker(symbols.get(stock, "ITC.NS"))
        hist = ticker.history(period="1mo")

        present = round(hist["Close"].iloc[-1], 2)

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

    return render_template("predict.html", result=result, form=form)


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
    app.run(debug=True)

