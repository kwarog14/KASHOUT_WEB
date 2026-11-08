import os
import math
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, flash, redirect, render_template_string,
    request, session, url_for
)

SECRET_KEY = os.environ.get("SECRET_KEY")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

if not SECRET_KEY or not ADMIN_USERNAME or not ADMIN_PASSWORD:
    raise RuntimeError(
        "Itakda ang SECRET_KEY, ADMIN_USERNAME, at ADMIN_PASSWORD "
        "sa environment variables."
    )

app = Flask(__name__)
app.secret_key = SECRET_KEY
DB_PATH = os.environ.get("DATABASE_PATH", "kashout.db")

BG = "#080D18"
PANEL = "#101A2B"
CARD = "#16243A"
CARD_LIGHT = "#20314B"
TEXT = "#F4F6FC"
MUTED = "#9BAAC2"
PURPLE = "#8055F6"
GREEN = "#25D79A"
RED = "#FF647C"


def connect_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                balance REAL NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL,
                date TEXT NOT NULL,
                details TEXT DEFAULT '',
                balance_after REAL
            )
        """)

        columns = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(transactions)"
            ).fetchall()
        }
        if "balance_after" not in columns:
            db.execute(
                "ALTER TABLE transactions ADD COLUMN balance_after REAL"
            )

        settings = db.execute(
            "SELECT balance FROM settings WHERE id = 1"
        ).fetchone()

        if settings is None:
            initial_balance = 8956.45
            db.execute(
                "INSERT INTO settings (id, balance) VALUES (1, ?)",
                (initial_balance,)
            )
            now = datetime.now().isoformat(timespec="seconds")
            db.executemany("""
                INSERT INTO transactions
                    (name, amount, type, date, details, balance_after)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                ("Mark Stonis", 45.00, "Cash Out", now,
                 "Cash withdrawal", initial_balance),
                ("Amino Randol", 45.00, "Cash Out", now,
                 "Cash withdrawal", initial_balance),
                ("Account", 500.00, "Cash In", now,
                 "Balance deposit", initial_balance),
            ])


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def fetch_data():
    with connect_db() as db:
        setting = db.execute(
            "SELECT balance FROM settings WHERE id = 1"
        ).fetchone()
        transactions = db.execute(
            "SELECT * FROM transactions ORDER BY id DESC"
        ).fetchall()

    balance = float(setting["balance"]) if setting else 0.0
    return balance, transactions


def totals_for(transactions, transaction_type):
    return sum(
        float(item["amount"])
        for item in transactions
        if item["type"] == transaction_type
    )


def monthly_cash_out(transactions):
    now = datetime.now()
    return sum(
        float(item["amount"])
        for item in transactions
        if item["type"] == "Cash Out"
        and datetime.fromisoformat(item["date"]).year == now.year
        and datetime.fromisoformat(item["date"]).month == now.month
    )


def monthly_chart(transactions):
    now = datetime.now()
    months = []

    for offset in range(5, -1, -1):
        month_number = now.month - offset
        year = now.year
        while month_number <= 0:
            month_number += 12
            year -= 1
        months.append((year, month_number))

    results = []
    for year, month in months:
        amount = sum(
            float(item["amount"])
            for item in transactions
            if item["type"] == "Cash Out"
            and datetime.fromisoformat(item["date"]).year == year
            and datetime.fromisoformat(item["date"]).month == month
        )
        results.append({
            "label": datetime(year, month, 1).strftime("%b"),
            "amount": amount,
        })

    maximum = max((item["amount"] for item in results), default=0) or 1
    for item in results:
        item["height"] = max(4, int(item["amount"] / maximum * 100))
    return results


PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KASH OUT</title>
<style>
:root {
  --bg: #080D18; --panel: #101A2B; --card: #16243A;
  --light: #20314B; --text: #F4F6FC; --muted: #9BAAC2;
  --purple: #8055F6; --green: #25D79A; --red: #FF647C;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 14px "Segoe UI", Arial, sans-serif;
}
a { color: inherit; text-decoration: none; }
button, input, select {
  font: inherit;
}
.topbar {
  max-width: 1440px; margin: auto; padding: 18px 26px;
  display: flex; align-items: center; gap: 24px;
}
.brand { font-size: 19px; font-weight: 800; white-space: nowrap; }
.brand-mark { color: #A78BFA; }
.nav { display: flex; gap: 5px; flex-wrap: wrap; }
.nav a, .button {
  background: var(--light); color: var(--text); border: 0;
  border-radius: 7px; padding: 10px 14px; cursor: pointer;
  font-weight: 700; display: inline-block;
}
.nav a.active, .button.purple { background: var(--purple); }
.button.green { background: var(--green); color: #06152A; }
.button.red { background: var(--red); }
.button:hover, .nav a:hover { filter: brightness(1.12); }
.logout { margin-left: auto; }
main { max-width: 1440px; margin: auto; padding: 8px 26px 28px; }
h1, h2, h3, p { margin-top: 0; }
h1 { font-size: 25px; margin-bottom: 5px; }
h2 { font-size: 17px; }
.subtitle { color: var(--muted); margin: 4px 0 18px; }
.card {
  background: var(--card); border: 1px solid #293951;
  border-radius: 10px; padding: 15px; min-width: 0;
}
.card-title { font-size: 15px; margin: 0 0 14px; }
.dashboard-grid {
  display: grid; grid-template-columns: 1fr 1fr 1fr;
  gap: 16px; min-height: 570px;
}
.column { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.balance { font-size: 28px; font-weight: 800; margin: 3px 0; }
.muted { color: var(--muted); }
.row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.actions { display: flex; gap: 8px; margin-top: 14px; }
.actions .button { flex: 1; text-align: center; }
.detail-row { display:flex; justify-content:space-between; padding:9px 0; border-bottom:1px solid #263650; }
.transaction {
  display: flex; align-items: center; gap: 10px; background: var(--light);
  padding: 9px; border-radius: 7px; margin: 7px 0;
}
.initials {
  width: 38px; height: 38px; border-radius: 7px; background: #415987;
  display:grid; place-items:center; font-weight:700; flex:none;
}
.transaction-info { flex: 1; min-width: 0; }
.transaction-info small { display:block; color:var(--muted); margin-top:4px; }
.positive { color: var(--green); font-weight:700; white-space:nowrap; }
.negative { color: var(--red); font-weight:700; white-space:nowrap; }
.chart {
  height: 220px; display:flex; align-items:flex-end; justify-content:space-around;
  border-bottom:1px solid #34445A; padding:10px 4px 0; gap:8px;
}
.bar-wrap { height:100%; flex:1; display:flex; flex-direction:column; justify-content:flex-end; align-items:center; gap:6px; }
.bar { width:min(28px,70%); background:var(--purple); border-radius:5px 5px 0 0; min-height:4px; }
.bar-label { color:var(--muted); font-size:12px; margin-bottom:-20px; }
.bar-value { font-size:10px; color:var(--text); }
.page-cards { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin:16px 0; }
.stat-value { font-size:23px; font-weight:800; margin:6px 0 0; }
.form-card { max-width:720px; margin:16px auto; }
label { display:block; color:var(--muted); margin:10px 0 6px; }
input, select {
  width:100%; padding:11px; border:0; border-radius:6px;
  color:var(--text); background:var(--light);
}
form .button { width:100%; margin-top:14px; }
.table-wrap { overflow-x:auto; }
table { width:100%; border-collapse:collapse; min-width:650px; }
th, td { text-align:left; padding:12px 9px; border-bottom:1px solid #34445A; }
th { color:var(--muted); font-size:11px; }
.inline-form { display:inline; }
.inline-form button { border:0; cursor:pointer; padding:7px 9px; border-radius:5px; background:var(--red); color:white; }
.flash { background:#263954; border:1px solid #405577; padding:11px 14px; border-radius:7px; margin-bottom:12px; }
.modal {
  display:none; position:fixed; inset:0; background:#0009; z-index:5;
  align-items:center; justify-content:center; padding:16px;
}
.modal.open { display:flex; }
.modal-card { width:min(420px,100%); background:var(--panel); padding:22px; border-radius:10px; }
.login-page { min-height:100vh; display:grid; grid-template-columns:6fr 5fr; padding:26px; gap:24px; }
.login-brand, .login-form { border:1px solid #293951; border-radius:12px; padding:8%; }
.login-brand { background:#111A2D; display:flex; flex-direction:column; justify-content:center; }
.login-form { background:var(--panel); display:flex; align-items:center; justify-content:center; }
.login-inner { width:min(350px,100%); }
.login-brand h1 { font-size:38px; margin:45px 0 12px; }
.login-brand p { color:var(--muted); line-height:1.6; }
.feature { margin:12px 0; }
.receipt { max-width:520px; margin:25px auto; background:white; color:#17263C; padding:28px; border-radius:8px; }
.receipt-row { display:flex; justify-content:space-between; gap:16px; padding:9px 0; border-bottom:1px solid #ddd; }
@media(max-width:900px) {
  .dashboard-grid { grid-template-columns:1fr 1fr; }
  .dashboard-grid .column:last-child { grid-column:1/-1; }
  .topbar { flex-wrap:wrap; }
}
@media(max-width:620px) {
  .dashboard-grid, .page-cards { grid-template-columns:1fr; }
  .dashboard-grid .column:last-child { grid-column:auto; }
  main { padding:8px 14px 20px; }
  .topbar { padding:14px; }
  .login-page { grid-template-columns:1fr; padding:12px; }
  .login-brand { display:none; }
}
@media print {
  body { background:white; color:#17263C; }
  .topbar, .no-print { display:none !important; }
  .receipt { border:0; margin:0 auto; }
}
</style>
</head>
<body>

{% if page == "login" %}
<div class="login-page">
  <section class="login-brand">
    <div class="brand"><span class="brand-mark">◆</span> KASH OUT</div>
    <h1>Your money,<br>clearly managed.</h1>
    <p>A simple and organized way to manage cash, bills, and bank transfers.</p>
    <div class="feature">↗ &nbsp; Record cash in and cash out</div>
    <div class="feature">▤ &nbsp; Pay bills and transfer funds</div>
    <div class="feature">▣ &nbsp; View and print receipts</div>
    <small class="muted">CASH MANAGEMENT SYSTEM</small>
  </section>
  <section class="login-form">
    <div class="login-inner">
      <h1>Welcome back</h1>
      <p class="subtitle">Sign in to continue to your dashboard.</p>
      {% for message in get_flashed_messages() %}<div class="flash">{{ message }}</div>{% endfor %}
      <form method="post">
        <label>USERNAME</label>
        <input name="username" required autofocus>
        <label>PASSWORD</label>
        <input id="password" name="password" type="password" required>
        <label style="display:flex;align-items:center;gap:8px">
          <input type="checkbox" style="width:auto" onclick="togglePassword()">
          Show password
        </label>
        <button class="button purple" type="submit" style="width:100%;margin-top:16px">SIGN IN →</button>
      </form>
      <p class="muted" style="text-align:center;margin-top:22px">Secure access to your KASH OUT account</p>
    </div>
  </section>
</div>
<script>
function togglePassword() {
  const box = document.getElementById("password");
  box.type = box.type === "password" ? "text" : "password";
}
</script>

{% else %}
<header class="topbar">
  <div class="brand"><span class="brand-mark">◆</span> KASH OUT</div>
  <nav class="nav">
    {% for label, destination in nav_items %}
      <a class="{{ 'active' if page == destination else '' }}"
         href="{{ url_for('page_view', page_name=destination) }}">{{ label }}</a>
    {% endfor %}
  </nav>
  <a class="button logout" href="{{ url_for('logout') }}">Log Out</a>
</header>

<main>
  {% for message in get_flashed_messages() %}<div class="flash">{{ message }}</div>{% endfor %}

  {% if page == "receipt" %}
    <section class="receipt">
      <h2 style="text-align:center">KASH OUT</h2>
      <p style="text-align:center;color:#718096">CASH TRANSACTION RECEIPT</p>
      <hr>
      <div class="receipt-row"><span>Receipt</span><strong>KOUT-{{ "%06d"|format(item["id"]) }}</strong></div>
      <div class="receipt-row"><span>Date</span><strong>{{ item["date"] }}</strong></div>
      <div class="receipt-row"><span>Type</span><strong>{{ item["type"] }}</strong></div>
      <div class="receipt-row"><span>Customer</span><strong>{{ item["name"] }}</strong></div>
      <div class="receipt-row"><span>Amount</span><strong>₱{{ "%.2f"|format(item["amount"]) }}</strong></div>
      <div class="receipt-row"><span>Balance</span><strong>₱{{ "%.2f"|format(item["balance_after"] or 0) }}</strong></div>
      {% if item["details"] %}<div class="receipt-row"><span>Details</span><strong>{{ item["details"] }}</strong></div>{% endif %}
      <p style="text-align:center;margin-top:24px">Thank you for your visit!</p>
      <button class="button purple no-print" onclick="window.print()">PRINT RECEIPT</button>
      <a class="button no-print" href="{{ url_for('page_view', page_name='Activity') }}">BACK</a>
    </section>

  {% elif page == "Dashboard" %}
    <h1>Dashboard Overview</h1>
    <p class="subtitle">Your cash summary, bills, and recent activity</p>
    <div class="dashboard-grid">
      <div class="column">
        <section class="card">
          <h2 class="card-title">Current Balance</h2>
          <div class="balance">₱{{ "{:,.2f}".format(balance) }}</div>
          <p class="muted">Available cash balance</p>
          <div class="actions">
            <button class="button green" onclick="openModal('cashin')">+ Cash In</button>
            <button class="button purple" onclick="openModal('cashout')">Cash Out</button>
          </div>
        </section>
        <section class="card">
          <h2 class="card-title">Quick Actions</h2>
          <a class="button" href="{{ url_for('page_view', page_name='Pay Bills') }}">Pay Bills</a>
          <a class="button" href="{{ url_for('page_view', page_name='Bank Transfer') }}">Bank Transfer</a>
          {% if transactions %}
            <a class="button purple" href="{{ url_for('receipt', transaction_id=transactions[0]['id']) }}">Print Latest Receipt</a>
          {% endif %}
        </section>
        <section class="card">
          <h2 class="card-title">Recent Transactions</h2>
          {% for item in transactions[:4] %}
            <div class="transaction">
              <div class="initials">{{ item["name"][:2]|upper }}</div>
              <div class="transaction-info"><strong>{{ item["name"] }}</strong>
                <small>{{ item["type"] }} · {{ item["date"][:16] }}</small></div>
              <span class="{{ 'positive' if item['type'] == 'Cash In' else 'negative' }}">
                {{ '+' if item["type"] == "Cash In" else '-' }}₱{{ "{:,.2f}".format(item["amount"]) }}
              </span>
            </div>
          {% else %}<p class="muted">No transactions yet.</p>{% endfor %}
        </section>
      </div>

      <div class="column">
        <section class="card" style="flex:1">
          <h2 class="card-title">Monthly Cash Out</h2>
          <div class="balance">₱{{ "{:,.2f}".format(month_total) }}</div>
          <p class="muted">Cash-out transactions this month</p>
          <div class="chart">
            {% for month in chart %}
              <div class="bar-wrap">
                {% if month["amount"] %}<span class="bar-value">{{ "{:,.0f}".format(month["amount"]) }}</span>{% endif %}
                <div class="bar" style="height:{{ month['height'] }}%"></div>
                <span class="bar-label">{{ month["label"] }}</span>
              </div>
            {% endfor %}
          </div>
        </section>
      </div>

      <div class="column">
        <section class="card">
          <h2 class="card-title">Account Summary</h2>
          <p class="muted">Monthly Cash Out</p>
          <div class="balance" style="color:var(--purple)">₱{{ "{:,.2f}".format(month_total) }}</div>
        </section>
        <section class="card" style="flex:1">
          <h2 class="card-title">Account Details</h2>
          <div class="detail-row"><span class="muted">Transactions</span><strong>{{ transactions|length }}</strong></div>
          <div class="detail-row"><span class="muted">Cash In</span><strong>₱{{ "{:,.2f}".format(totals["Cash In"]) }}</strong></div>
          <div class="detail-row"><span class="muted">Bills Paid</span><strong>₱{{ "{:,.2f}".format(totals["Pay Bills"]) }}</strong></div>
          <div class="detail-row"><span class="muted">Bank Transfers</span><strong>₱{{ "{:,.2f}".format(totals["Bank Transfer"]) }}</strong></div>
        </section>
      </div>
    </div>

    <div id="cashin" class="modal" onclick="closeModal(event, 'cashin')">
      <div class="modal-card">
        <h2>Cash In</h2>
        <p class="muted">Enter the amount to add to the balance.</p>
        <form method="post" action="{{ url_for('add_transaction') }}">
          <input type="hidden" name="type" value="Cash In">
          <input type="hidden" name="name" value="Account">
          <input type="hidden" name="details" value="Cash transaction">
          <label>Amount (₱)</label><input name="amount" type="number" min="0.01" step="0.01" required>
          <button class="button green">CONFIRM CASH IN</button>
        </form>
        <button class="button" onclick="closeModal(null, 'cashin')">CLOSE</button>
      </div>
    </div>

    <div id="cashout" class="modal" onclick="closeModal(event, 'cashout')">
      <div class="modal-card">
        <h2>Cash Out</h2>
        <p class="muted">Enter the customer and amount.</p>
        <form method="post" action="{{ url_for('add_transaction') }}">
          <input type="hidden" name="type" value="Cash Out">
          <label>Customer name</label><input name="name" required>
          <input type="hidden" name="details" value="Cash transaction">
          <label>Amount (₱)</label><input name="amount" type="number" min="0.01" step="0.01" required>
          <button class="button purple">CONFIRM CASH OUT</button>
        </form>
        <button class="button" onclick="closeModal(null, 'cashout')">CLOSE</button>
      </div>
    </div>

  {% elif page == "Analytics" %}
    <h1>Analytics</h1>
    <p class="subtitle">Summary based on recorded transactions</p>
    <div class="page-cards">
      <section class="card"><span class="muted">Transactions</span><div class="stat-value">{{ transactions|length }}</div></section>
      <section class="card"><span class="muted">Monthly Cash Out</span><div class="stat-value">₱{{ "{:,.2f}".format(month_total) }}</div></section>
      <section class="card"><span class="muted">Current Balance</span><div class="stat-value">₱{{ "{:,.2f}".format(balance) }}</div></section>
    </div>
    <section class="card">
      <h2 class="card-title">Monthly Cash Out</h2>
      <div class="chart" style="height:300px">
        {% for month in chart %}
          <div class="bar-wrap">
            {% if month["amount"] %}<span class="bar-value">₱{{ "{:,.0f}".format(month["amount"]) }}</span>{% endif %}
            <div class="bar" style="height:{{ month['height'] }}%"></div>
            <span class="bar-label">{{ month["label"] }}</span>
          </div>
        {% endfor %}
      </div>
    </section>

  {% elif page == "Activity" %}
    <div class="row"><h1>Activity</h1></div>
    <section class="card">
      <h2 class="card-title">Select a transaction</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>DATE</th><th>TRANSACTION</th><th>NAME / MERCHANT</th><th>AMOUNT</th><th>ACTIONS</th></tr></thead>
          <tbody>
          {% for item in transactions %}
            <tr>
              <td>{{ item["date"][:16] }}</td><td>{{ item["type"] }}</td>
              <td>{{ item["name"] }}</td>
              <td>{{ '+' if item["type"] == "Cash In" else '-' }}₱{{ "{:,.2f}".format(item["amount"]) }}</td>
              <td>
                <a class="button purple" href="{{ url_for('receipt', transaction_id=item['id']) }}">Receipt</a>
                <form class="inline-form" method="post" action="{{ url_for('delete_transaction', transaction_id=item['id']) }}" onsubmit="return confirm('Delete this transaction?')">
                  <button>Delete</button>
                </form>
              </td>
            </tr>
          {% else %}<tr><td colspan="5">No transactions yet.</td></tr>{% endfor %}
          </tbody>
        </table>
      </div>
    </section>

  {% elif page == "Pay Bills" %}
    <h1>Pay Bills</h1>
    <p class="subtitle">Record a bill payment from your current balance.</p>
    <section class="card form-card">
      <h2 class="card-title">Bill Payment</h2>
      <form method="post" action="{{ url_for('add_transaction') }}">
        <input type="hidden" name="type" value="Pay Bills">
        <label>Biller / Company</label><input name="name" required>
        <label>Account or reference number</label><input name="details" required>
        <label>Amount (₱)</label><input name="amount" type="number" min="0.01" step="0.01" required>
        <p class="muted">Available balance: ₱{{ "{:,.2f}".format(balance) }}</p>
        <button class="button purple">PAY BILL</button>
      </form>
    </section>

  {% elif page == "Bank Transfer" %}
    <h1>Bank Transfer</h1>
    <p class="subtitle">Record a transfer from your current balance.</p>
    <section class="card form-card">
      <h2 class="card-title">Transfer Details</h2>
      <form method="post" action="{{ url_for('add_transaction') }}">
        <input type="hidden" name="type" value="Bank Transfer">
        <label>Bank name</label><input name="bank" required>
        <label>Recipient name</label><input name="name" required>
        <label>Account number</label><input name="account" required>
        <label>Amount (₱)</label><input name="amount" type="number" min="0.01" step="0.01" required>
        <p class="muted">Available balance: ₱{{ "{:,.2f}".format(balance) }}</p>
        <button class="button purple">TRANSFER</button>
      </form>
    </section>
  {% endif %}
</main>
<script>
function openModal(id) {
  document.getElementById(id).classList.add("open");
}
function closeModal(event, id) {
  if (!event || event.target.id === id) {
    document.getElementById(id).classList.remove("open");
  }
}
</script>
{% endif %}
</body>
</html>
"""


NAV_ITEMS = [
    ("Dashboard", "Dashboard"),
    ("Analytics", "Analytics"),
    ("Activity", "Activity"),
    ("Pay Bills", "Pay Bills"),
    ("Bank Transfer", "Bank Transfer"),
]


def render_page(page, **extra):
    balance, transactions = fetch_data()
    totals = {
        kind: totals_for(transactions, kind)
        for kind in ("Cash In", "Pay Bills", "Bank Transfer")
    }
    return render_template_string(
        PAGE,
        page=page,
        logged_in=True,
        nav_items=NAV_ITEMS,
        balance=balance,
        transactions=transactions,
        totals=totals,
        month_total=monthly_cash_out(transactions),
        chart=monthly_chart(transactions),
        **extra
    )


@app.route("/")
@login_required
def home():
    return render_page("Dashboard")


@app.route("/page/<page_name>")
@login_required
def page_view(page_name):
    allowed_pages = {"Dashboard", "Analytics", "Activity", "Pay Bills", "Bank Transfer"}
    if page_name not in allowed_pages:
        return redirect(url_for("home"))
    return render_page(page_name)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("home"))
        flash("The username or password is incorrect.")
    return render_template_string(PAGE, page="login", logged_in=False)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/transaction", methods=["POST"])
@login_required
def add_transaction():
    kind = request.form.get("type", "")
    name = request.form.get("name", "").strip()
    details = request.form.get("details", "").strip()

    if kind == "Bank Transfer":
        bank = request.form.get("bank", "").strip()
        account = request.form.get("account", "").strip()
        details = f"{bank} · Account: {account}"
        if not bank or not account:
            flash("Pakilagay ang bank at account number.")
            return redirect(request.referrer or url_for("home"))

    if kind == "Pay Bills" and details:
        details = f"Reference: {details}"

    try:
        amount = float(request.form.get("amount", "").replace(",", ""))
    except ValueError:
        flash("Maglagay ng valid na amount.")
        return redirect(request.referrer or url_for("home"))

    allowed_types = {"Cash In", "Cash Out", "Pay Bills", "Bank Transfer"}
    if (
        kind not in allowed_types or not name
        or not math.isfinite(amount) or amount <= 0
    ):
        flash("Pakisuri ang transaction details.")
        return redirect(request.referrer or url_for("home"))

    change = amount if kind == "Cash In" else -amount

    with connect_db() as db:
        settings = db.execute(
            "SELECT balance FROM settings WHERE id = 1"
        ).fetchone()
        current_balance = float(settings["balance"])

        if change < 0 and amount > current_balance:
            flash("Insufficient current balance.")
            return redirect(request.referrer or url_for("home"))

        new_balance = current_balance + change
        db.execute(
            "UPDATE settings SET balance = ? WHERE id = 1",
            (new_balance,)
        )
        db.execute("""
            INSERT INTO transactions
                (name, amount, type, date, details, balance_after)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            name, amount, kind,
            datetime.now().isoformat(timespec="seconds"),
            details, new_balance
        ))

    flash(f"{kind} of ₱{amount:,.2f} recorded.")
    return redirect(request.referrer or url_for("home"))


@app.route("/delete/<int:transaction_id>", methods=["POST"])
@login_required
def delete_transaction(transaction_id):
    with connect_db() as db:
        item = db.execute(
            "SELECT amount, type FROM transactions WHERE id = ?",
            (transaction_id,)
        ).fetchone()

        if item is None:
            flash("Transaction not found.")
            return redirect(url_for("page_view", page_name="Activity"))

        amount = float(item["amount"])
        change = amount if item["type"] == "Cash In" else -amount

        db.execute(
            "UPDATE settings SET balance = balance - ? WHERE id = 1",
            (change,)
        )
        db.execute("""
            UPDATE transactions
            SET balance_after = balance_after - ?
            WHERE id > ? AND balance_after IS NOT NULL
        """, (change, transaction_id))
        db.execute(
            "DELETE FROM transactions WHERE id = ?",
            (transaction_id,)
        )

    flash("Transaction deleted. Balance updated.")
    return redirect(url_for("page_view", page_name="Activity"))


@app.route("/receipt/<int:transaction_id>")
@login_required
def receipt(transaction_id):
    with connect_db() as db:
        item = db.execute(
            "SELECT * FROM transactions WHERE id = ?",
            (transaction_id,)
        ).fetchone()

    if item is None:
        flash("Transaction not found.")
        return redirect(url_for("page_view", page_name="Activity"))

    return render_page("receipt", item=item)


init_db()

if __name__ == "__main__":
    app.run(debug=False)