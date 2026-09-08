from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
import re

app = Flask(__name__)

# Secret key for login session
app.secret_key = "chobrima-secret-key-change-this-later"

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chobrima.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# Order database table
class Order(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(20), unique=True, nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(120), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default="PENDING")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Create database
with app.app_context():
    db.create_all()


# Home
@app.route("/")
def home():
    return render_template("index.html")


# Checkout
@app.route("/checkout")
def checkout():
    return render_template("checkout.html")


# Payment
@app.route("/payment", methods=["POST"])
def payment():

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()

    if not name:
        return """
        <h2>Invalid Name ❌</h2>
        <p>Please enter your name.</p>
        <a href="/checkout">Go Back</a>
        """

    email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    if not re.match(email_pattern, email):
        return """
        <h2>Invalid Email Address ❌</h2>
        <p>Please enter a valid email address.</p>
        <a href="/checkout">Go Back</a>
        """

    return render_template(
        "payment.html",
        name=name,
        email=email
    )


# Payment success
@app.route("/payment-success", methods=["POST"])
def payment_success():

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()

    order_id = "CB-" + uuid.uuid4().hex[:8].upper()

    order = Order(
        order_id=order_id,
        customer_name=name,
        customer_email=email,
        product_name="Blessed Forever Design V.1",
        amount=99,
        status="PAID"
    )

    db.session.add(order)
    db.session.commit()

    return f"""
    <h1>Payment Successful! ✅</h1>

    <p>Thank you, {name}!</p>

    <h2>Order ID: {order_id}</h2>

    <p>Product: Blessed Forever Design V.1</p>
    <p>Amount Paid: ₱99</p>
    <p>Status: PAID</p>

    <p>Download will be available shortly.</p>

    <br>

    <a href="/">Back to Store</a>
    """


# =========================
# ADMIN LOGIN
# =========================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # Temporary admin credentials
        if username == "admin" and password == "123456":

            session["admin_logged_in"] = True

            return redirect(url_for("admin"))

        return render_template(
            "admin_login.html",
            error="Invalid username or password."
        )

    return render_template("admin_login.html")


# =========================
# ADMIN DASHBOARD
# =========================

@app.route("/admin")
def admin():

    # Check login
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    orders = Order.query.order_by(
        Order.created_at.desc()
    ).all()

    total_orders = len(orders)

    total_sales = sum(
        order.amount
        for order in orders
        if order.status == "PAID"
    )

    return render_template(
        "admin.html",
        orders=orders,
        total_orders=total_orders,
        total_sales=total_sales
    )


# =========================
# ADMIN LOGOUT
# =========================

@app.route("/admin/logout")
def admin_logout():

    session.pop("admin_logged_in", None)

    return redirect(url_for("admin_login"))


# Run application
if __name__ == "__main__":
    app.run(debug=True)