from flask import Flask, render_template, request, redirect, url_for, session, send_file
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, UTC, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import os 
load_dotenv()
import re
import phonenumbers
import requests
import secrets
import hashlib
from io import BytesIO

app = Flask(__name__)

def saudi_time(dt):
    if not dt:
        return ""

    return (
        dt.replace(tzinfo=UTC) + timedelta(hours=3)
    ).strftime("%d %b %Y, %I:%M %p")


app.jinja_env.filters["saudi_time"] = saudi_time

# =========================
# SECRET KEY
# =========================

app.secret_key = "chobrima-secret-key-change-this-later"


# =========================
# DOWNLOAD FILE
# =========================

DOWNLOAD_FOLDER = os.path.join(
    app.root_path,
    "downloads"
)

PRODUCT_FILE = os.path.join(
    DOWNLOAD_FOLDER,
    "Blessed-Forever-Design-V1-SAMPLE.zip"
)


# =========================
# DATABASE
# =========================

database_url = os.getenv("DATABASE_URL")

if database_url:
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = (
    database_url or "sqlite:///chobrima.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# SUPABASE STORAGE
# =========================

from supabase import create_client

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SECRET_KEY")

supabase = create_client(
    supabase_url,
    supabase_key
)

# =========================
# CLOUDFLARE TURNSTILE
# =========================

turnstile_site_key = os.getenv(
    "TURNSTILE_SITE_KEY"
)

turnstile_secret_key = os.getenv(
    "TURNSTILE_SECRET_KEY"
)

app.jinja_env.globals[
    "turnstile_site_key"
] = turnstile_site_key


def get_product_image_url(image_path):

    if not image_path:
        return ""


    # New Supabase Storage image
    if image_path.startswith("supabase:"):

        storage_path = image_path.replace(
            "supabase:",
            "",
            1
        ).lstrip("/")

        return supabase.storage.from_(
            "product-images"
        ).get_public_url(storage_path)


    # Existing local image
    return url_for(
        "static",
        filename=(
            image_path
            if image_path.startswith("uploads/")
            else "images/" + image_path
        )
    )

    def upload_to_supabase_storage(file, bucket_name, storage_path, content_type):
        """
        Upload a Flask uploaded file to Supabase Storage.
        """

        file_bytes = file.read()

        print(
            "UPLOADING TO SUPABASE:",
            bucket_name,
            storage_path,
            "SIZE:",
            len(file_bytes)
        )

        supabase.storage.from_(bucket_name).upload(
            storage_path,
            file_bytes,
            file_options={
                "content-type": content_type
            }
        )

        return storage_path


app.jinja_env.globals["get_product_image_url"] = (
    get_product_image_url
)

# =========================
# ORDER TABLE
# =========================

class Order(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    order_id = db.Column(
        db.String(20),
        unique=True,
        nullable=False
    )

    customer_name = db.Column(
        db.String(100),
        nullable=False
    )

    customer_email = db.Column(
        db.String(120),
        nullable=False
    )

    customer_mobile = db.Column(
    db.String(30),
    nullable=False
    )

    product_name = db.Column(
        db.String(200),
        nullable=False
    )

    amount = db.Column(
        db.Float,
        nullable=False
    )

    status = db.Column(
        db.String(30),
        default="PENDING"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================
# DOWNLOAD TABLE
# =========================

class Download(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(
        db.String(20),
        unique=True,
        nullable=False
    )

    product_id = db.Column(
        db.Integer,
        nullable=True
    )

    token_hash = db.Column(
        db.String(64),
        unique=True,
        nullable=False
    )

    download_count = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    downloaded_at = db.Column(
        db.DateTime,
        nullable=True
    )

# =========================
# ADMIN USER TABLE
# =========================

class AdminUser(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

# PRODUCT TABLE
class Product(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    product_name = db.Column(db.String(200), nullable=False)

    description = db.Column(db.Text, nullable=True)

    category = db.Column(db.String(100), nullable=False)

    price = db.Column(db.Float, nullable=False, default=0)

    product_type = db.Column(db.String(10), nullable=False, default="PAID")

    preview_image = db.Column(db.String(255), nullable=False)

    thumbnail_2 = db.Column(db.String(255), nullable=True)

    thumbnail_3 = db.Column(db.String(255), nullable=True)

    thumbnail_4 = db.Column(db.String(255), nullable=True)

    product_file = db.Column(db.String(255), nullable=True)

    active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ContactMessage(db.Model):

    __tablename__ = "contact_messages"

    id = db.Column(
        db.BigInteger,
        primary_key=True
    )

    full_name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        nullable=False
    )

    mobile = db.Column(
        db.String(30),
        nullable=False
    )

    subject = db.Column(
        db.String(150),
        nullable=True
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="NEW"
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now()
    )

class ProductComment(db.Model):

    __tablename__ = "product_comments"

    id = db.Column(
        db.BigInteger,
        primary_key=True
    )

    product_id = db.Column(
        db.BigInteger,
        nullable=False
    )

    country_code = db.Column(
        db.String(10),
        nullable=True
    )

    country_name = db.Column(
        db.String(100),
        nullable=True
    )

    customer_name = db.Column(
        db.String(100),
        nullable=False
    )

    rating = db.Column(
        db.Integer,
        nullable=False,
        default=5
    )

    comment = db.Column(
        db.Text,
        nullable=False
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="VISIBLE"
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now()
    )

# =========================
# CREATE DATABASE TABLES
# =========================

with app.app_context():

    db.create_all()

    # Create default admin if none exists
    existing_admin = AdminUser.query.filter_by(
        username="admin"
    ).first()

    if not existing_admin:

        default_admin = AdminUser(
            username="admin",
            password_hash=generate_password_hash("123456")
        )

        db.session.add(default_admin)
        db.session.commit()


# =========================
# HOME
@app.route("/")
def home():
    products = Product.query.filter_by(active=True).order_by(
        Product.created_at.desc()
    ).all()

    return render_template(
        "index.html",
        products=products
    )

# PAYMONGO WEBHOOK
@app.route("/paymongo/webhook", methods=["POST"])
def paymongo_webhook():
    import hmac
    import hashlib
    import time

    webhook_secret = os.getenv("PAYMONGO_WEBHOOK_SECRET")

    if not webhook_secret:
        print("❌ PAYMONGO_WEBHOOK_SECRET is missing")
        return {"status": "server configuration error"}, 500

    # IMPORTANT:
    # Get the RAW request body before parsing JSON.
    raw_body = request.get_data()

    signature_header = request.headers.get("Paymongo-Signature", "")

    if not signature_header:
        print("❌ Missing Paymongo-Signature header")
        return {"status": "missing signature"}, 400

    # Parse:
    # t=timestamp,te=test_signature,li=live_signature
    signature_parts = {}

    for part in signature_header.split(","):
        if "=" in part:
            key, value = part.split("=", 1)
            signature_parts[key] = value

    timestamp = signature_parts.get("t")
    test_signature = signature_parts.get("te")
    live_signature = signature_parts.get("li")

    if not timestamp:
        print("❌ Missing webhook timestamp")
        return {"status": "invalid signature"}, 400

    # Our current webhook is TEST MODE.
    received_signature = test_signature

    if not received_signature:
        print("❌ Missing test signature")
        return {"status": "invalid signature"}, 400

    # Optional replay protection:
    # Reject requests older than 5 minutes.
    try:
        timestamp_int = int(timestamp)
        if abs(time.time() - timestamp_int) > 300:
            print("❌ Webhook timestamp too old")
            return {"status": "expired signature"}, 400
    except ValueError:
        print("❌ Invalid webhook timestamp")
        return {"status": "invalid timestamp"}, 400

    # PayMongo signature:
    # HMAC-SHA256(timestamp + "." + raw_body)
    signed_payload = timestamp.encode() + b"." + raw_body

    expected_signature = hmac.new(
        webhook_secret.encode(),
        signed_payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(
        expected_signature,
        received_signature
    ):
        print("❌ INVALID PAYMONGO WEBHOOK SIGNATURE")
        return {"status": "invalid signature"}, 400

    print("✅ PAYMONGO WEBHOOK SIGNATURE VERIFIED")

    # Only parse JSON AFTER signature verification.
    payload = request.get_json(silent=True)

    if not payload:
        print("❌ Invalid JSON payload")
        return {"status": "invalid payload"}, 400

    event_data = payload.get("data", {})
    event_attributes = event_data.get("attributes", {})

    event_type = event_attributes.get("type")

    print("🔔 PAYMONGO WEBHOOK RECEIVED")
    print("Event Type:", event_type)

    if event_type == "checkout_session.payment.paid":
        print("💰 CHECKOUT PAYMENT PAID EVENT RECEIVED")

    # Acknowledge PayMongo.
    return {"status": "received"}, 200

# =========================
# PRODUCT DETAIL
# =========================

@app.route("/product/<int:product_id>")
def product(product_id):

    product = Product.query.filter_by(
        id=product_id,
        active=True
    ).first_or_404()

    return render_template(
        "product.html",
        product=product
    )

# =========================
# CHECKOUT
# =========================

# CHECKOUT
@app.route("/checkout")
def checkout():

    product_id = request.args.get("product_id", type=int)

    if not product_id:
        return redirect(url_for("home"))

    product = Product.query.filter_by(
        id=product_id,
        active=True
    ).first()

    if not product:
        return """
        <h2>Product Not Found ❌</h2>
        <p>The selected product is not available.</p>
        <a href="/">Back to Store</a>
        """

    return render_template(
        "checkout.html",
        product=product
    )


# =========================
# PAYMENT
# =========================

@app.route(
    "/payment",
    methods=["POST"]
)
def payment():

    name = request.form.get(
        "name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    product_id = request.form.get(
        "product_id",
        type=int
    )

    # ==================================================
    # NAME VALIDATION
    # ==================================================

    if not name or len(name) < 2:
        return render_template(
            "form_error.html",
            error_title="Invalid Name",
            error_message="Please enter your complete name.",
            error_detail="Your name is required before continuing to payment.",
            error_icon="✕",
            suggestion=None,
            back_url=url_for(
                "checkout",
                product_id=product_id
            ) if product_id else url_for("home"),
            back_text="GO BACK TO CHECKOUT"
        )

    # ==================================================
    # EMAIL FORMAT VALIDATION
    # ==================================================

    email_pattern = (
        r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
        r"@[A-Za-z0-9-]+"
        r"(?:\.[A-Za-z0-9-]{2,})+$"
    )

    if not email or not re.match(
        email_pattern,
        email
    ):
        return render_template(
            "form_error.html",
            error_title="Invalid Email Address",
            error_message="Please enter a valid email address.",
            error_detail="Check your email address and try again.",
            error_icon="✕",
            suggestion=None,
            back_url=url_for(
                "checkout",
                product_id=product_id
            ) if product_id else url_for("home"),
            back_text="GO BACK TO CHECKOUT"
        )

    # ==================================================
    # EMAIL DOMAIN CHECK
    # ==================================================

    email_domain = email.split("@")[-1]

    if (
        email_domain.startswith("-")
        or email_domain.endswith("-")
        or ".." in email_domain
    ):
        return render_template(
            "form_error.html",
            error_title="Invalid Email Address",
            error_message="Please check your email address and try again.",
            error_detail="The email domain appears to be invalid.",
            error_icon="✕",
            suggestion=None,
            back_url=url_for(
                "checkout",
                product_id=product_id
            ) if product_id else url_for("home"),
            back_text="GO BACK TO CHECKOUT"
        )

    # ==================================================
    # COMMON EMAIL TYPO CHECK
    # ==================================================

    common_email_typos = {
        "gmail.cm": "gmail.com",
        "gmail.con": "gmail.com",
        "gmail.co": "gmail.com",
        "gmai.com": "gmail.com",
        "gmial.com": "gmail.com",
        "yaho.com": "yahoo.com",
        "yahoo.con": "yahoo.com",
        "hotmai.com": "hotmail.com",
        "hotmail.con": "hotmail.com",
        "outlok.com": "outlook.com",
        "outlook.con": "outlook.com",
    }

    if email_domain in common_email_typos:

        correct_domain = common_email_typos[
            email_domain
        ]

        email_username = email.split("@")[0]

        return render_template(
            "form_error.html",
            error_title="Check Your Email Address",
            error_message="Did you mean the correct email address?",
            error_detail="Please go back and correct your email address.",
            error_icon="⚠",
            suggestion=f"""
                Suggested email:<br>
                <strong>
                    {email_username}@{correct_domain}
                </strong>
            """,
            back_url=url_for(
                "checkout",
                product_id=product_id
            ),
            back_text="GO BACK TO CHECKOUT"
        )

    # ==================================================
    # PRODUCT ID VALIDATION
    # ==================================================

    if not product_id:
        return render_template(
            "form_error.html",
            error_title="Invalid Product",
            error_message="No product was selected.",
            error_detail="Please return to the store and select a product.",
            error_icon="✕",
            suggestion=None,
            back_url=url_for("home"),
            back_text="BACK TO STORE"
        )

    # ==================================================
    # GET PRODUCT
    # ==================================================

    product = Product.query.filter_by(
        id=product_id,
        active=True
    ).first()

    if not product:
        return render_template(
            "form_error.html",
            error_title="Product Not Found",
            error_message="The selected product is not available.",
            error_detail="This product may have been removed or hidden.",
            error_icon="✕",
            suggestion=None,
            back_url=url_for("home"),
            back_text="BACK TO STORE"
        )

    # ==================================================
    # CHECK DIGITAL FILE
    # ==================================================

    if not product.product_file:
        return render_template(
            "form_error.html",
            error_title="Digital File Not Available",
            error_message="This product does not have a digital file yet.",
            error_detail="Please try another product or contact Chobrima Prints.",
            error_icon="✕",
            suggestion=None,
            back_url=url_for("home"),
            back_text="BACK TO STORE"
        )

    # ==================================================
    # PAYMONGO SECRET KEY
    # ==================================================

    paymongo_secret_key = os.getenv(
        "PAYMONGO_SECRET_KEY"
    )

    if not paymongo_secret_key:
        print("❌ PAYMONGO_SECRET_KEY is missing")

        return render_template(
            "form_error.html",
            error_title="Payment System Unavailable",
            error_message="Payment is temporarily unavailable.",
            error_detail="Please try again later.",
            error_icon="✕",
            suggestion=None,
            back_url=url_for(
                "checkout",
                product_id=product.id
            ),
            back_text="GO BACK TO CHECKOUT"
        )

    # ==================================================
    # GENERATE CHOBRIMA ORDER ID
    # ==================================================

    order_id = (
        "CB-"
        + uuid.uuid4().hex[:8].upper()
    )

    # ==================================================
    # GENERATE SECURE DOWNLOAD TOKEN
    # ==================================================

    raw_token = secrets.token_urlsafe(32)

    token_hash = hashlib.sha256(
        raw_token.encode()
    ).hexdigest()

    # ==================================================
    # CREATE PENDING ORDER
    # ==================================================

    order = Order(
        order_id=order_id,
        customer_name=name,
        customer_email=email,
        customer_mobile="",
        product_name=product.product_name,
        amount=product.price,
        status="PENDING"
    )

    db.session.add(order)

    # ==================================================
    # CREATE DOWNLOAD RECORD
    # ==================================================

    download = Download(
        order_id=order_id,
        product_id=product.id,
        token_hash=token_hash,
        download_count=0
    )

    db.session.add(download)

    db.session.commit()

    # ==================================================
    # SAVE ORDER + TOKEN IN SESSION
    # ==================================================

    session["success_order_id"] = order_id
    session["success_download_token"] = raw_token

    # ==================================================
    # PAYMONGO CHECKOUT SESSION
    # ==================================================

    amount_centavos = int(
        round(product.price * 100)
    )

    success_url = url_for(
        "payment_success",
        order_id=order_id,
        _external=True
    )

    cancel_url = url_for(
        "checkout",
        product_id=product.id,
        _external=True
    )

    payload = {
        "data": {
            "attributes": {

                "line_items": [
                    {
                        "name": product.product_name,
                        "amount": amount_centavos,
                        "currency": "PHP",
                        "quantity": 1
                    }
                ],

                "payment_method_types": [
                    "card",
                    "gcash",
                    "qrph"
                ],

                "success_url": success_url,

                "cancel_url": cancel_url,

                "reference_number": order_id,

                "send_email_receipt": True,

                "metadata": {
                    "order_id": order_id,
                    "product_id": str(product.id)
                }
            }
        }
    }

    try:

        response = requests.post(
            "https://api.paymongo.com/v2/checkout_sessions",

            auth=(
                paymongo_secret_key,
                ""
            ),

            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Idempotency-Key": order_id
            },

            json=payload,

            timeout=30
        )

    except requests.RequestException as exc:

        print(
            "❌ PAYMONGO CONNECTION ERROR:",
            exc
        )

        db.session.delete(download)
        db.session.delete(order)
        db.session.commit()

        session.pop(
            "success_order_id",
            None
        )

        session.pop(
            "success_download_token",
            None
        )

        return render_template(
            "form_error.html",
            error_title="Payment Connection Error",
            error_message="We could not connect to the payment gateway.",
            error_detail="Please try again in a few moments.",
            error_icon="✕",
            suggestion=None,
            back_url=url_for(
                "checkout",
                product_id=product.id
            ),
            back_text="GO BACK TO CHECKOUT"
        )

    # ==================================================
    # CHECK PAYMONGO RESPONSE
    # ==================================================

    if response.status_code != 200:

        print(
            "❌ PAYMONGO ERROR:",
            response.status_code
        )

        print(
            response.text
        )

        db.session.delete(download)
        db.session.delete(order)
        db.session.commit()

        session.pop(
            "success_order_id",
            None
        )

        session.pop(
            "success_download_token",
            None
        )

        return render_template(
            "form_error.html",
            error_title="Payment Error",
            error_message="We could not create your payment session.",
            error_detail="Please try again or contact Chobrima Prints.",
            error_icon="✕",
            suggestion=None,
            back_url=url_for(
                "checkout",
                product_id=product.id
            ),
            back_text="GO BACK TO CHECKOUT"
        )

    # ==================================================
    # GET PAYMONGO CHECKOUT URL
    # ==================================================

    paymongo_data = response.json()

    checkout_url = (
        paymongo_data
        .get("data", {})
        .get("attributes", {})
        .get("checkout_url")
    )

    if not checkout_url:

        print(
            "❌ PAYMONGO CHECKOUT URL MISSING"
        )

        db.session.delete(download)
        db.session.delete(order)
        db.session.commit()

        session.pop(
            "success_order_id",
            None
        )

        session.pop(
            "success_download_token",
            None
        )

        return render_template(
            "form_error.html",
            error_title="Payment Error",
            error_message="Payment checkout could not be opened.",
            error_detail="Please try again later.",
            error_icon="✕",
            suggestion=None,
            back_url=url_for(
                "checkout",
                product_id=product.id
            ),
            back_text="GO BACK TO CHECKOUT"
        )

    print(
        "✅ PAYMONGO CHECKOUT CREATED:",
        order_id
    )

    # ==================================================
    # REDIRECT CUSTOMER TO PAYMONGO
    # ==================================================

    return redirect(
        checkout_url
    )

@app.route("/place-order")
def place_order():

    product_id = request.args.get(
        "product_id",
        type=int
    )

    if not product_id:
        return redirect(
            url_for("home")
        )

    product = Product.query.filter_by(
        id=product_id,
        active=True
    ).first()

    if not product:
        return """
        <h2>Product Not Found ❌</h2>
        <p>The selected product is not available.</p>
        <a href="/">Back to Store</a>
        """

    return render_template(
        "order_form.html",
        product=product,
        turnstile_site_key=os.getenv(
            "TURNSTILE_SITE_KEY"
        )
    )

# =========================
# PLACE ORDER
# =========================

@app.route(
    "/place-order-submit",
    methods=["POST"]
)
@app.route(
    "/place-order-submit",
    methods=["POST"]
)
def place_order_submit():

    name = request.form.get(
        "name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    mobile = request.form.get(
        "mobile",
        ""
    ).strip()

    product_id = request.form.get(
        "product_id",
        type=int
    )

    # =========================
    # VALIDATE NAME
    # =========================

    if not name or len(name) < 2:
        return render_template(
            "form_error.html",
            error_title="Invalid Name",
            error_message="Please enter your complete name.",
            error_detail="Your name is required before placing your order.",
            error_icon="✕",
            suggestion=None,
            back_url=(
                url_for(
                    "place_order",
                    product_id=product_id
                )
                if product_id
                else url_for("home")
            ),
            back_text="GO BACK TO ORDER FORM"
        )

    # =========================
    # VALIDATE EMAIL
    # =========================

    email_pattern = (
        r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
        r"@[A-Za-z0-9-]+"
        r"(?:\.[A-Za-z0-9-]{2,})+$"
    )

    if not email or not re.match(
        email_pattern,
        email
    ):
        return render_template(
            "form_error.html",
            error_title="Invalid Email Address",
            error_message="Please enter a valid email address.",
            error_detail="Check your email address and try again.",
            error_icon="✕",
            suggestion=None,
            back_url=(
                url_for(
                    "place_order",
                    product_id=product_id
                )
                if product_id
                else url_for("home")
            ),
            back_text="GO BACK TO ORDER FORM"
        )

    # =========================
    # COMMON EMAIL TYPOS
    # =========================

    email_domain = email.split("@")[-1]

    common_email_typos = {
        "gmail.cm": "gmail.com",
        "gmail.con": "gmail.com",
        "gmail.co": "gmail.com",
        "gmai.com": "gmail.com",
        "gmial.com": "gmail.com",
        "yaho.com": "yahoo.com",
        "yahoo.con": "yahoo.com",
        "hotmai.com": "hotmail.com",
        "hotmail.con": "hotmail.com",
        "outlok.com": "outlook.com",
        "outlook.con": "outlook.com",
    }

    if email_domain in common_email_typos:

        correct_domain = common_email_typos[
            email_domain
        ]

        email_username = email.split("@")[0]

        return render_template(
            "form_error.html",
            error_title="Check Your Email Address",
            error_message="Did you mean the correct email address?",
            error_detail="Please go back and correct your email address.",
            error_icon="⚠",
            suggestion=f"""
                Suggested email:<br>
                <strong>
                    {email_username}@{correct_domain}
                </strong>
            """,
            back_url=url_for(
                "place_order",
                product_id=product_id
            ),
            back_text="GO BACK TO ORDER FORM"
        )

    # =========================
    # VALIDATE INTERNATIONAL MOBILE
    # =========================

    try:

        phone_number = phonenumbers.parse(
            mobile,
            None
        )

        valid_mobile = (
            phonenumbers.is_valid_number(
                phone_number
            )
            and phonenumbers.is_possible_number(
                phone_number
            )
        )

    except phonenumbers.NumberParseException:

        valid_mobile = False

    if not mobile or not valid_mobile:

        return render_template(
            "form_error.html",
            error_title="Invalid Mobile Number",
            error_message="Please enter a valid mobile or WhatsApp number.",
            error_detail=(
                "Please include the international country code, "
                "for example: +966512345678 or +639171234567."
            ),
            error_icon="✕",
            suggestion=None,
            back_url=(
                url_for(
                    "place_order",
                    product_id=product_id
                )
                if product_id
                else url_for("home")
            ),
            back_text="GO BACK TO ORDER FORM"
        )

    # =========================
    # CLOUDFLARE TURNSTILE
    # =========================

    turnstile_token = request.form.get(
        "cf-turnstile-response",
        ""
    ).strip()

    if not turnstile_token:

        return render_template(
            "form_error.html",
            error_title="Verification Required",
            error_message="Please complete the anti-spam verification.",
            error_detail="Confirm that you are human before placing your order.",
            error_icon="⚠",
            suggestion=None,
            back_url=(
                url_for(
                    "place_order",
                    product_id=product_id
                )
                if product_id
                else url_for("home")
            ),
            back_text="GO BACK TO ORDER FORM"
        )

    turnstile_response = requests.post(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data={
            "secret": os.getenv(
                "TURNSTILE_SECRET_KEY"
            ),
            "response": turnstile_token,
            "remoteip": request.remote_addr
        },
        timeout=10
    )

    turnstile_result = turnstile_response.json()

    if not turnstile_result.get("success"):

        return render_template(
            "form_error.html",
            error_title="Verification Failed",
            error_message="Anti-spam verification failed.",
            error_detail="Please try again and complete the verification.",
            error_icon="✕",
            suggestion=None,
            back_url=(
                url_for(
                    "place_order",
                    product_id=product_id
                )
                if product_id
                else url_for("home")
            ),
            back_text="GO BACK TO ORDER FORM"
        )

    # =========================
    # VALIDATE PRODUCT
    # =========================

    if not product_id:

        return render_template(
            "form_error.html",
            error_title="Invalid Product",
            error_message="No product was selected.",
            error_detail="Please return to the store and select a product.",
            error_icon="✕",
            suggestion=None,
            back_url=url_for("home"),
            back_text="BACK TO STORE"
        )

    product = Product.query.filter_by(
        id=product_id,
        active=True
    ).first()

    if not product:

        return render_template(
            "form_error.html",
            error_title="Product Not Found",
            error_message="The selected product is not available.",
            error_detail="This product may have been removed or hidden.",
            error_icon="✕",
            suggestion=None,
            back_url=url_for("home"),
            back_text="BACK TO STORE"
        )

    # =========================
    # CREATE PENDING ORDER
    # =========================

    order_id = (
        "CB-"
        + uuid.uuid4().hex[:8].upper()
    )

    order = Order(
        order_id=order_id,
        customer_name=name,
        customer_email=email,
        customer_mobile=mobile,
        product_name=product.product_name,
        amount=product.price,
        status="PENDING"
    )

    db.session.add(order)
    db.session.commit()

    # =========================
    # SUCCESS
    # =========================

    return render_template(
        "order_pending.html",
        order=order,
        product=product
    )
# =========================
# PAYMENT SUCCESS
# =========================

@app.route("/payment-success", methods=["POST", "GET"])
def payment_success():

    # ==================================================
    # GET REQUEST
    # Show existing successful order
    # ==================================================

    if request.method == "GET":

        order_id = session.get("success_order_id")
        raw_token = session.get("success_download_token")

        if not order_id or not raw_token:
            return redirect(url_for("home"))

        order = Order.query.filter_by(
            order_id=order_id
        ).first()

        if not order:
            return redirect(url_for("home"))

        product = Product.query.filter_by(
            product_name=order.product_name
        ).first()

        if not product:
            return redirect(url_for("home"))

        download_link = url_for(
            "secure_download",
            token=raw_token,
            _external=True
        )

        return render_template(
    "payment_success.html",
    order=order,
    product=product,
    download_link=download_link
)

    # ==================================================
    # POST REQUEST
    # Create payment/order ONLY ONCE
    # ==================================================

    name = request.form.get(
        "name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip()

    product_id = request.form.get(
        "product_id",
        type=int
    )

    # ==================================================
    # CUSTOMER VALIDATION
    # ==================================================

    if not name:
        return """
        <h2>Invalid Name ❌</h2>
        <p>Please enter your name.</p>
        <a href="/checkout">Go Back</a>
        """

    # ==================================================
    # EMAIL VALIDATION
    # ==================================================

    email_pattern = (
        r"^[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+"
        r"\.[A-Za-z]{2,}$"
    )

    if not re.match(
        email_pattern,
        email
    ):
        return """
        <h2>Invalid Email Address ❌</h2>
        <p>Please enter a valid email address.</p>
        <a href="/checkout">Go Back</a>
        """

    # ==================================================
    # PRODUCT VALIDATION
    # ==================================================

    if not product_id:
        return """
        <h2>Invalid Product ❌</h2>
        <p>No product was selected.</p>
        <a href="/">Back to Store</a>
        """

    product = Product.query.filter_by(
        id=product_id,
        active=True
    ).first()

    if not product:
        return """
        <h2>Product Not Found ❌</h2>
        <p>The selected product is not available.</p>
        <a href="/">Back to Store</a>
        """

    if not product.product_file:
        return """
        <h2>Digital File Not Available ❌</h2>
        <p>This product does not have a digital file yet.</p>
        <a href="/">Back to Store</a>
        """

    # ==================================================
    # GENERATE ORDER ID
    # ==================================================

    order_id = (
        "CB-"
        + uuid.uuid4().hex[:8].upper()
    )

    # ==================================================
    # CREATE ORDER
    # ==================================================

    order = Order(
        order_id=order_id,
        customer_name=name,
        customer_email=email,
        product_name=product.product_name,
        amount=product.price,
        status="PAID"
    )

    db.session.add(order)

    # ==================================================
    # GENERATE DOWNLOAD TOKEN
    # ==================================================

    raw_token = secrets.token_urlsafe(32)

    token_hash = hashlib.sha256(
        raw_token.encode()
    ).hexdigest()

    # ==================================================
    # CREATE DOWNLOAD RECORD
    # ==================================================

    download = Download(
        order_id=order_id,
        product_id=product.id,
        token_hash=token_hash,
        download_count=0
    )

    db.session.add(download)

    db.session.commit()

    # ==================================================
    # SAVE ORDER + TOKEN IN SESSION
    # ==================================================

    session["success_order_id"] = order_id

    session["success_download_token"] = raw_token

    # ==================================================
    # REDIRECT TO SUCCESS PAGE
    # ==================================================

    return redirect(
        url_for("payment_success")
    )

# =========================
# SECURE ONE-TIME DOWNLOAD
# =========================

@app.route("/download/<token>")
def secure_download(token):

    token_hash = hashlib.sha256(
        token.encode()
    ).hexdigest()

    download = Download.query.filter_by(
        token_hash=token_hash
    ).first()

    # ==================================================
    # INVALID DOWNLOAD LINK
    # ==================================================

    if not download:

        return render_template(
            "download_error.html",
            error_title="Invalid Download Link",
            error_message="This download link is not valid.",
            error_detail="The link may be expired, incorrect, or no longer available.",
            error_icon="✕"
        )

    # ==================================================
    # GET ORDER
    # ==================================================

    order = Order.query.filter_by(
        order_id=download.order_id
    ).first()

    # ==================================================
    # ORDER NOT FOUND
    # ==================================================

    if not order:

        return render_template(
            "download_error.html",
            error_title="Order Not Found",
            error_message="We could not find this order.",
            error_detail="The order associated with this download link could not be found.",
            error_icon="✕"
        )

    # ==================================================
    # DOWNLOAD NOT AVAILABLE
    # ==================================================

    if order.status not in ["PAID", "FREE"]:

        return render_template(
            "download_error.html",
            error_title="Download Not Available",
            error_message="This order is not available for download.",
            error_detail="This order has not been completed or paid.",
            error_icon="✕"
        )

    # ==================================================
    # ONE-TIME DOWNLOAD CHECK
    # ==================================================

    print(
        "DOWNLOAD COUNT CHECK:",
        download.download_count
    )

    if download.download_count >= 1:

        print(
            "🚫 DOWNLOAD BLOCKED - ALREADY USED"
        )

        return render_template(
            "download_error.html",
            error_title="Download Already Used",
            error_message="This download link can only be used once.",
            error_detail="The product has already been downloaded.",
            error_icon="✕"
        )

    # ==================================================
    # GET PRODUCT
    # ==================================================

    product = Product.query.filter_by(
        id=download.product_id
    ).first()

    # ==================================================
    # PRODUCT NOT FOUND
    # ==================================================

    if not product:

        return render_template(
            "download_error.html",
            error_title="Product Not Found",
            error_message="The purchased product could not be found.",
            error_detail="The digital product associated with this order is no longer available.",
            error_icon="✕"
        )

    # ==================================================
    # FILE NOT AVAILABLE
    # ==================================================

    if not product.product_file:

        return render_template(
            "download_error.html",
            error_title="File Not Available",
            error_message="The digital product file is currently unavailable.",
            error_detail="Please contact Chobrima Prints if you believe this is an error.",
            error_icon="✕"
        )

    # ==================================================
    # GET PRODUCT FILE
    # ==================================================

    if product.product_file.startswith("supabase:"):

        storage_path = product.product_file.replace(
            "supabase:",
            "",
            1
        ).lstrip("/")

        try:

            file_bytes = supabase.storage.from_(
                "product-files"
            ).download(
                storage_path
            )

        except Exception as e:

            print(
                "SUPABASE DOWNLOAD ERROR:",
                repr(e)
            )

            return render_template(
                "download_error.html",
                error_title="File Not Available",
                error_message="The digital product file is currently unavailable.",
                error_detail="Please try again later or contact Chobrima Prints for assistance.",
                error_icon="✕"
            )

        product_filename = os.path.basename(
            storage_path
        )

        product_file_data = BytesIO(
            file_bytes
        )

    else:

        # ==================================================
        # OLD LOCAL FILE SUPPORT
        # ==================================================

        product_folder = os.path.join(
            app.root_path,
            "downloads",
            "products"
        )

        product_filename = os.path.basename(
            product.product_file
        )

        product_file_path = os.path.join(
            product_folder,
            product_filename
        )

        if not os.path.isfile(
            product_file_path
        ):

            return render_template(
                "download_error.html",
                error_title="File Not Available",
                error_message="The digital product file is currently unavailable.",
                error_detail="Please try again later or contact Chobrima Prints for assistance.",
                error_icon="✕"
            )

        product_file_data = product_file_path

    # ==================================================
    # MARK DOWNLOAD AS USED
    # ==================================================

    download.download_count = 1

    download.downloaded_at = datetime.now(UTC)

    print(
        "DOWNLOAD COUNT BEFORE COMMIT:",
        download.download_count
    )

    db.session.commit()

    print(
        "DOWNLOAD COUNT AFTER COMMIT:",
        download.download_count
    )

    # ==================================================
    # SEND FILE
    # ==================================================

    return send_file(
        product_file_data,
        as_attachment=True,
        download_name=product_filename
    )

# =========================
# FREE PRODUCT DOWNLOAD
# =========================

@app.route("/free-download/<int:product_id>")
def free_download(product_id):

    product = Product.query.get_or_404(product_id)

    if not product.active:
        return """
        <div style="text-align:center; margin-top:100px; font-family:Arial;">
            <h2>Product Not Available ❌</h2>
            <p>This product is currently unavailable.</p>
            <a href="/">Back to Store</a>
        </div>
        """

    if product.product_type != "FREE":
        return redirect(
            url_for("product", product_id=product.id)
        )

    if not product.product_file:
        return """
        <div style="text-align:center; margin-top:100px; font-family:Arial;">
            <h2>File Not Available ❌</h2>
            <p>The free digital product file is currently unavailable.</p>
            <a href="/">Back to Store</a>
        </div>
        """

    # ==========================================
    # CHECK EXISTING FREE DOWNLOAD IN SESSION
    # ==========================================

    session_order_key = f"free_order_{product.id}"
    session_token_key = f"free_token_{product.id}"

    existing_order_id = session.get(session_order_key)
    existing_token = session.get(session_token_key)

    if existing_order_id and existing_token:

        download = Download.query.filter_by(
            order_id=existing_order_id
        ).first()

        if download:
            return redirect(
                url_for(
                    "secure_download",
                    token=existing_token
                )
            )

        # Remove stale session data
        session.pop(session_order_key, None)
        session.pop(session_token_key, None)

    # ==========================================
    # CREATE NEW FREE DOWNLOAD
    # ==========================================

    order_id = "FREE-" + uuid.uuid4().hex[:8].upper()

    order = Order(
        order_id=order_id,
        customer_name=name,
        customer_email=email,
        customer_mobile="",
        product_name=product.product_name,
        amount=product.price,
        status="PAID"
    )

    db.session.add(order)

    # Generate secure one-time token
    raw_token = secrets.token_urlsafe(32)

    token_hash = hashlib.sha256(
        raw_token.encode()
    ).hexdigest()

    download = Download(
        order_id=order_id,
        product_id=product.id,
        token_hash=token_hash,
        download_count=0
    )

    db.session.add(download)

    db.session.commit()

    # Save this download to the browser session
    session[session_order_key] = order_id
    session[session_token_key] = raw_token

    # Start secure download
    return redirect(
        url_for(
            "secure_download",
            token=raw_token
        )
    )

# =========================
# ADMIN LOGIN
# =========================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )


        # Find admin account

        admin_user = AdminUser.query.filter_by(
            username=username
        ).first()


        # Check password

        if (
            admin_user
            and check_password_hash(
                admin_user.password_hash,
                password
            )
        ):

            session["admin_logged_in"] = True

            session["admin_user_id"] = admin_user.id

            return redirect(
                url_for("admin")
            )


        return render_template(

            "admin_login.html",

            error="Invalid username or password."

        )


    return render_template(
        "admin_login.html"
    )

def upload_to_supabase_storage(file, bucket_name, storage_path, content_type):
    """
    Upload a Flask uploaded file to Supabase Storage.
    """

    file_bytes = file.read()

    supabase.storage.from_(bucket_name).upload(
        storage_path,
        file_bytes,
        file_options={
            "content-type": content_type
        }
    )

    return storage_path

# =========================
# CONTACT US
# =========================

@app.route("/contact", methods=["GET", "POST"])
def contact():

    if request.method == "POST":

        full_name = request.form.get(
            "full_name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        mobile = request.form.get(
            "mobile",
            ""
        ).strip()

        subject = request.form.get(
            "subject",
            ""
        ).strip()

        message = request.form.get(
            "message",
            ""
        ).strip()

        # =========================
        # BASIC VALIDATION
        # =========================

        if not full_name:
            return render_template(
                "contact.html",
                error="Please enter your complete name."
            )

        if len(full_name) < 3:
            return render_template(
                "contact.html",
                error="Please enter your complete name."
            )

        if not email:
            return render_template(
                "contact.html",
                error="Please enter your email address."
            )

        if not mobile:
            return render_template(
                "contact.html",
                error="Please enter your mobile or WhatsApp number."
            )

        if not message:
            return render_template(
                "contact.html",
                error="Please enter your message."
            )

        # =========================
        # EMAIL VALIDATION
        # =========================

        email_pattern = (
            r"^[A-Za-z0-9._%+-]+"
            r"@[A-Za-z0-9.-]+"
            r"\.[A-Za-z]{2,}$"
        )

        if not re.match(
            email_pattern,
            email
        ):
            return render_template(
                "contact.html",
                error="Please enter a valid email address."
            )

        # =========================
        # MOBILE VALIDATION
        # =========================

        mobile_clean = re.sub(
            r"[\s().-]",
            "",
            mobile
        )

        mobile_pattern = (
            r"^\+?[0-9]{8,15}$"
        )

        if not re.match(
            mobile_pattern,
            mobile_clean
        ):
            return render_template(
                "contact.html",
                error="Please enter a valid mobile or WhatsApp number."
            )

        # =========================
        # LENGTH VALIDATION
        # =========================

        if len(subject) > 150:
            return render_template(
                "contact.html",
                error="Subject is too long."
            )

        if len(message) > 2000:
            return render_template(
                "contact.html",
                error="Message is too long."
            )

        # =========================
        # CLOUDFLARE TURNSTILE
        # =========================

        turnstile_token = request.form.get(
            "cf-turnstile-response",
            ""
        ).strip()

        if not turnstile_token:
            return render_template(
                "contact.html",
                error="Please complete the anti-spam verification."
            )

        try:

            turnstile_response = requests.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": turnstile_secret_key,
                    "response": turnstile_token,
                    "remoteip": request.remote_addr
                },
                timeout=10
            )

            turnstile_result = (
                turnstile_response.json()
            )

            if not turnstile_result.get(
                "success"
            ):
                return render_template(
                    "contact.html",
                    error="Anti-spam verification failed. Please try again."
                )

        except requests.RequestException:

            return render_template(
                "contact.html",
                error="Verification service is temporarily unavailable. Please try again."
            )

        # =========================
        # SAVE MESSAGE
        # =========================

        contact_message = ContactMessage(

            full_name=full_name,

            email=email,

            mobile=mobile_clean,

            subject=subject or None,

            message=message,

            status="NEW"
        )

        db.session.add(
            contact_message
        )

        db.session.commit()

        return render_template(
            "contact.html",
            success="Thank you! Your message has been sent successfully."
        )

    return render_template(
        "contact.html"
    )

# =========================
# PRODUCT COMMENTS
# =========================

@app.route(
    "/product/<int:product_id>/comment",
    methods=["POST"]
)
def add_product_comment(product_id):

    product = Product.query.get_or_404(product_id)

    # =========================
    # CLOUDFLARE TURNSTILE
    # =========================

    turnstile_token = request.form.get(
        "cf-turnstile-response",
        ""
    )

    if not turnstile_token:
        print("❌ TURNSTILE TOKEN MISSING")
        return redirect(
            url_for(
                "product",
                product_id=product.id
            )
        )

    try:

        turnstile_response = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={
                "secret": turnstile_secret_key,
                "response": turnstile_token,
                "remoteip": request.remote_addr
            },
            timeout=10
        )

        turnstile_result = (
            turnstile_response.json()
        )

        if not turnstile_result.get("success"):
            print("❌ TURNSTILE FAILED:")
            print(turnstile_result)

            return redirect(
                url_for(
                    "product",
                    product_id=product.id
                )
            )

    except requests.RequestException:

        return redirect(
            url_for(
                "product",
                product_id=product.id
            )
        )

    # =========================
    # GET FORM DATA
    # =========================

    customer_name = request.form.get(
        "customer_name",
        ""
    ).strip()

    comment = request.form.get(
        "comment",
        ""
    ).strip()


    # =========================
    # VALIDATION
    # =========================

    if not customer_name:
        return redirect(
            url_for(
                "product",
                product_id=product.id
            )
        )

    if len(customer_name) < 2:
        return redirect(
            url_for(
                "product",
                product_id=product.id
            )
        )

    if len(customer_name) > 100:
        return redirect(
            url_for(
                "product",
                product_id=product.id
            )
        )

    if not comment:
        return redirect(
            url_for(
                "product",
                product_id=product.id
            )
        )

    if len(comment) > 1000:
        return redirect(
            url_for(
                "product",
                product_id=product.id
            )
        )


    # =========================
    # AUTOMATIC COUNTRY DETECTION
    # =========================

    country_code = None
    country_name = None

    visitor_ip = request.remote_addr

    try:

        if visitor_ip not in [
            "127.0.0.1",
            "::1",
            "localhost"
        ]:

            geo_response = requests.get(
                f"https://ipapi.co/{visitor_ip}/json/",
                timeout=5
            )

            if geo_response.ok:

                geo_data = geo_response.json()

                country_code = geo_data.get(
                    "country_code"
                )

                country_name = geo_data.get(
                    "country_name"
                )

                print(
                    "🌍 COUNTRY DETECTED:",
                    country_code,
                    country_name
                )

    except requests.RequestException as e:

        print(
            "⚠️ COUNTRY DETECTION FAILED:"
        )

        print(e)


    # =========================
    # SAVE COMMENT
    # =========================

    new_comment = ProductComment(
        product_id=product.id,
        country_code=country_code,
        country_name=country_name,
        customer_name=customer_name,
        rating=5,
        comment=comment,
        status="VISIBLE"
    )

    db.session.add(new_comment)

    db.session.commit()


    # =========================
    # BACK TO PRODUCT
    # =========================

    return redirect(
        url_for(
            "product",
            product_id=product.id
        )
    )

    # =========================
    # GET FORM DATA
    # =========================

    customer_name = request.form.get(
        "customer_name",
        ""
    ).strip()

    comment = request.form.get(
        "comment",
        ""
    ).strip()

    rating = request.form.get(
        "rating",
        type=int
    )

    # =========================
    # VALIDATION
    # =========================

    if not customer_name:
        return redirect(
            url_for(
                "product",
                product_id=product.id
            )
        )

    if len(customer_name) < 2:
        return redirect(
            url_for(
                "product",
                product_id=product.id
            )
        )

    if len(customer_name) > 100:
        return redirect(
            url_for(
                "product",
                product_id=product.id
            )
        )

    if not comment:
        return redirect(
            url_for(
                "product",
                product_id=product.id
            )
        )

    if len(comment) > 1000:
        return redirect(
            url_for(
                "product",
                product_id=product.id
            )
        )

    if rating is None:
        rating = 5

    if rating < 1 or rating > 5:
        rating = 5

    # =========================
    # SAVE COMMENT
    # =========================

    new_comment = ProductComment(
        product_id=product.id,
        customer_name=customer_name,
        rating=rating,
        comment=comment,
        status="VISIBLE"
    )

    db.session.add(new_comment)
    db.session.commit()

    return redirect(
        url_for(
            "product",
            product_id=product.id
        )
    )

# =========================
# ADMIN CONTACT MESSAGES
# =========================

@app.route("/admin/contact-messages")
def admin_contact_messages():

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    messages = ContactMessage.query.order_by(
        ContactMessage.created_at.desc()
    ).all()

    return render_template(
        "contact_messages.html",
        messages=messages
    )


# =========================
# MARK CONTACT MESSAGE AS READ
# =========================

@app.route(
    "/admin/contact-messages/read/<int:message_id>",
    methods=["POST"]
)
def mark_contact_message_read(message_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    message = ContactMessage.query.get_or_404(message_id)

    message.status = "READ"

    db.session.commit()

    return redirect(
        url_for("admin_contact_messages")
    )

# ADD PRODUCT
@app.route("/admin/products/add", methods=["GET", "POST"])
def add_product():

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    if request.method == "POST":

        product_name = request.form.get(
            "product_name", ""
        ).strip()

        description = request.form.get(
            "description", ""
        ).strip()

        category = request.form.get(
            "category", ""
        ).strip()

        product_type = request.form.get(
            "product_type",
            "PAID"
        ).strip().upper()

        price_text = request.form.get(
            "price", ""
        ).strip()

        preview_image = request.files.get(
            "preview_image"
        )

        thumbnail_2 = request.files.get(
            "thumbnail_2"
        )

        thumbnail_3 = request.files.get(
            "thumbnail_3"
        )

        thumbnail_4 = request.files.get(
            "thumbnail_4"
        )

        product_file = request.files.get(
            "product_file"
        )

                # BASIC VALIDATION

        if not product_name:

            return render_template(
                "add_product.html",
                error="Product name is required."
            )

        if not category:

            return render_template(
                "add_product.html",
                error="Category is required."
            )

        if product_type not in ["FREE", "PAID"]:

            return render_template(
                "add_product.html",
                error="Invalid product type."
            )

        if product_type == "FREE":

            price = 0.0

        else:

            try:

                price = float(price_text)

            except (TypeError, ValueError):

                return render_template(
                    "add_product.html",
                    error="Please enter a valid price."
                )

            if price < 0:

                return render_template(
                    "add_product.html",
                    error="Price cannot be negative."
                )
    

        # CHECK PREVIEW IMAGE

        if not preview_image or preview_image.filename == "":

            return render_template(
                "add_product.html",
                error="Please upload a preview image."
            )

        # CHECK DIGITAL ZIP

        if not product_file or product_file.filename == "":

            return render_template(
                "add_product.html",
                error="Please upload the digital product ZIP file."
            )

        # ALLOWED IMAGE TYPES

        allowed_images = {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp"
        }

        # CHECK MAIN PREVIEW IMAGE

        image_extension = os.path.splitext(
            preview_image.filename
        )[1].lower()

        if image_extension not in allowed_images:

            return render_template(
                "add_product.html",
                error="Invalid preview image. Use JPG, PNG or WebP."
            )

        # CHECK OPTIONAL THUMBNAILS

        thumbnail_files = [
            thumbnail_2,
            thumbnail_3,
            thumbnail_4
        ]

        thumbnail_extensions = []

        for thumbnail in thumbnail_files:

            if thumbnail and thumbnail.filename:

                extension = os.path.splitext(
                    thumbnail.filename
                )[1].lower()

                if extension not in allowed_images:

                    return render_template(
                        "add_product.html",
                        error="Invalid thumbnail image. Use JPG, PNG or WebP."
                    )

                thumbnail_extensions.append(
                    extension
                )

            else:

                thumbnail_extensions.append(
                    None
                )

        # CHECK ZIP

        product_extension = os.path.splitext(
            product_file.filename
        )[1].lower()

        if product_extension != ".zip":

            return render_template(
                "add_product.html",
                error="Invalid digital product file. ZIP files only."
            )

        # CREATE SAFE UNIQUE FILENAMES

        safe_id = uuid.uuid4().hex

        image_filename = (
            safe_id + image_extension
        )

        product_filename = (
            safe_id + ".zip"
        )

        # SUPABASE STORAGE PATHS

        image_storage_path = (
            "products/" + image_filename
        )

        product_storage_path = (
            "products/" + product_filename
        )

        thumbnail_storage_paths = [
            None,
            None,
            None
        ]

        try:

            # UPLOAD MAIN PREVIEW IMAGE

            upload_to_supabase_storage(
                preview_image,
                "product-images",
                image_storage_path,
                preview_image.mimetype or "image/png"
            )

            # UPLOAD OPTIONAL THUMBNAILS

            for index, thumbnail in enumerate(
                thumbnail_files
            ):

                if thumbnail and thumbnail.filename:

                    thumbnail_filename = (
                        safe_id
                        + f"-thumb-{index + 2}"
                        + thumbnail_extensions[index]
                    )

                    thumbnail_storage_path = (
                        "products/"
                        + thumbnail_filename
                    )

                    upload_to_supabase_storage(
                        thumbnail,
                        "product-images",
                        thumbnail_storage_path,
                        thumbnail.mimetype or "image/png"
                    )

                    thumbnail_storage_paths[index] = (
                        thumbnail_storage_path
                    )

            # UPLOAD PRIVATE ZIP

            upload_to_supabase_storage(
                product_file,
                "product-files",
                product_storage_path,
                "application/zip"
            )

            print(
                "ZIP UPLOAD SUCCESS:",
                product_storage_path
            )

        except Exception as e:

            print(
                "SUPABASE STORAGE UPLOAD ERROR:",
                e
            )

            return render_template(
                "add_product.html",
                error="File upload failed. Please try again."
            )

        # CREATE PRODUCT

        product = Product(

            product_name=product_name,

            description=description,

            category=category,

            product_type=product_type,

            price=price,

            # MAIN IMAGE

            preview_image=(
                "supabase:" + image_storage_path
            ),

            # THUMBNAIL 2

            thumbnail_2=(
                "supabase:" + thumbnail_storage_paths[0]
                if thumbnail_storage_paths[0]
                else None
            ),

            # THUMBNAIL 3

            thumbnail_3=(
                "supabase:" + thumbnail_storage_paths[1]
                if thumbnail_storage_paths[1]
                else None
            ),

            # THUMBNAIL 4

            thumbnail_4=(
                "supabase:" + thumbnail_storage_paths[2]
                if thumbnail_storage_paths[2]
                else None
            ),

            # PRIVATE ZIP

            product_file=(
                "supabase:" + product_storage_path
            ),

            active=True
        )

        db.session.add(product)

        db.session.commit()

        return redirect(
            url_for("admin")
        )

    return render_template(
        "add_product.html"
    )
# =========================
# ADMIN DASHBOARD
# =========================

@app.route("/admin")
def admin():



    if not session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for("admin_login")
        )


    orders = Order.query.order_by(
        Order.created_at.desc()
    ).all()
    


    total_orders = len(orders)


    total_sales = sum(

        order.amount

        for order in orders

        if order.status == "PAID"

    )

    products = Product.query.order_by(
        Product.created_at.desc()
    ).all()

    for p in products:
        print(
            "PRODUCT ZIP:",
            p.id,
            p.product_name,
            "=>",
            p.product_file
        )

    downloads = Download.query.all()


    download_lookup = {

        download.order_id: download

        for download in downloads

    }

    # COUNT NEW CONTACT MESSAGES
    new_contact_messages = ContactMessage.query.filter_by(
    status="NEW"
    ).count()

    return render_template(
    "admin.html",
    orders=orders,
    total_orders=total_orders,
    total_sales=total_sales,
    download_lookup=download_lookup,
    products=products,
    new_contact_messages=new_contact_messages
)

@app.route("/admin/order/<order_id>")
def admin_order_details(order_id):
    order = Order.query.filter_by(order_id=order_id).first()

    if not order:
        return render_template(
            "download_error.html",
            title="Order Not Found",
            message="The selected order could not be found.",
            detail="Please return to the Admin Dashboard and try again.",
            icon="❌"
        )

    return render_template(
        "admin_order_details.html",
        order=order
    )

@app.route("/admin/order/<order_id>/update-status", methods=["POST"])
def update_order_status(order_id):

    order = Order.query.filter_by(
        order_id=order_id
    ).first()

    if not order:
        return "Order not found", 404

    new_status = request.form.get("status")

    allowed_statuses = [
        "PENDING",
        "CONFIRMED",
        "PROCESSING",
        "COMPLETED",
        "CANCELLED"
    ]

    if new_status not in allowed_statuses:
        return "Invalid order status", 400

    order.status = new_status

    db.session.commit()

    return redirect(
        url_for(
            "admin",
            updated=order.order_id
        )
    )

# =========================
# DELETE CUSTOMER ORDER
# =========================

@app.route(
    "/admin/orders/delete/<int:order_id>",
    methods=["POST"]
)
def delete_order(order_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    order = Order.query.get_or_404(order_id)

    download = Download.query.filter_by(
        order_id=order.order_id
    ).first()

    try:

        if download:
            db.session.delete(download)

        db.session.delete(order)

        db.session.commit()

    except Exception:
        db.session.rollback()
        return "Unable to delete order.", 500

    return redirect(url_for("admin"))

@app.route("/admin/products/toggle/<int:product_id>")
def toggle_product(product_id):


    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    product = Product.query.get_or_404(product_id)

    product.active = not product.active

    db.session.commit()

    return redirect(url_for("admin"))

# EDIT PRODUCT
@app.route("/admin/products/edit/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):

    print("EDIT PRODUCT POST RECEIVED")

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    product = Product.query.get_or_404(product_id)

    if request.method == "POST":

        product_name = request.form.get(
            "product_name", ""
        ).strip()

        description = request.form.get(
            "description", ""
        ).strip()

        category = request.form.get(
            "category", ""
        ).strip()

        product_type = request.form.get(
            "product_type",
            "PAID"
        ).strip().upper()

        price_text = request.form.get(
            "price", ""
        ).strip()

        preview_image = request.files.get(
            "preview_image"
        )

        thumbnail_2 = request.files.get(
            "thumbnail_2"
        )

        thumbnail_3 = request.files.get(
            "thumbnail_3"
        )

        thumbnail_4 = request.files.get(
            "thumbnail_4"
        )

        product_file = request.files.get(
            "product_file"
        )

                # BASIC VALIDATION

        if not product_name:

            return render_template(
                "edit_product.html",
                product=product,
                error="Product name is required."
            )

        if not category:

            return render_template(
                "edit_product.html",
                product=product,
                error="Category is required."
            )

        if product_type not in ["FREE", "PAID"]:

            return render_template(
                "edit_product.html",
                product=product,
                error="Invalid product type."
            )

        if product_type == "FREE":

            price = 0.0

        else:

            try:

                price = float(price_text)

            except (TypeError, ValueError):

                return render_template(
                    "edit_product.html",
                    product=product,
                    error="Please enter a valid price."
                )

            if price < 0:

                return render_template(
                    "edit_product.html",
                    product=product,
                    error="Price cannot be negative."
                )

        # UPDATE BASIC INFORMATION

        product.product_name = product_name
        product.description = description
        product.category = category
        product.price = price

        # ALLOWED IMAGE TYPES

        allowed_images = {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp"
        }

        # UPDATE PREVIEW IMAGE

        if preview_image and preview_image.filename:

            image_extension = os.path.splitext(
                preview_image.filename
            )[1].lower()

            if image_extension not in allowed_images:

                return render_template(
                    "edit_product.html",
                    product=product,
                    error="Invalid preview image. Use JPG, PNG or WebP."
                )

            safe_id = uuid.uuid4().hex

            image_filename = (
                safe_id + image_extension
            )

            image_storage_path = (
                "products/" + image_filename
            )

            try:

                upload_to_supabase_storage(
                    preview_image,
                    "product-images",
                    image_storage_path,
                    preview_image.mimetype or "image/png"
                )

            except Exception as e:

                print(
                    "SUPABASE IMAGE UPLOAD ERROR:",
                    e
                )

                return render_template(
                    "edit_product.html",
                    product=product,
                    error="Preview image upload failed. Please try again."
                )

            # DELETE OLD SUPABASE IMAGE

            if product.preview_image and product.preview_image.startswith(
                "supabase:"
            ):

                old_image_path = product.preview_image.replace(
                    "supabase:",
                    "",
                    1
                ).lstrip("/")

                try:

                    supabase.storage.from_(
                        "product-images"
                    ).remove([
                        old_image_path
                    ])

                except Exception as e:

                    print(
                        "OLD SUPABASE IMAGE DELETE ERROR:",
                        e
                    )

            # DELETE OLD LOCAL IMAGE

            elif product.preview_image:

                old_image_path = os.path.join(
                    app.root_path,
                    "static",
                    product.preview_image
                )

                if os.path.isfile(old_image_path):

                    os.remove(old_image_path)

            product.preview_image = (
                "supabase:" + image_storage_path
            )

        # UPDATE THUMBNAILS

        thumbnail_data = [
            ("thumbnail_2", thumbnail_2),
            ("thumbnail_3", thumbnail_3),
            ("thumbnail_4", thumbnail_4)
        ]

        for field_name, thumbnail in thumbnail_data:

            if thumbnail and thumbnail.filename:

                thumbnail_extension = os.path.splitext(
                    thumbnail.filename
                )[1].lower()

                if thumbnail_extension not in allowed_images:

                    return render_template(
                        "edit_product.html",
                        product=product,
                        error="Invalid thumbnail image. Use JPG, PNG or WebP."
                    )

                safe_id = uuid.uuid4().hex

                thumbnail_filename = (
                    safe_id
                    + "-"
                    + field_name
                    + thumbnail_extension
                )

                thumbnail_storage_path = (
                    "products/"
                    + thumbnail_filename
                )

                try:

                    upload_to_supabase_storage(
                        thumbnail,
                        "product-images",
                        thumbnail_storage_path,
                        thumbnail.mimetype or "image/png"
                    )

                except Exception as e:

                    print(
                        "SUPABASE THUMBNAIL UPLOAD ERROR:",
                        e
                    )

                    return render_template(
                        "edit_product.html",
                        product=product,
                        error=f"{field_name} upload failed. Please try again."
                    )

                # DELETE OLD THUMBNAIL

                old_thumbnail = getattr(
                    product,
                    field_name
                )

                if old_thumbnail and old_thumbnail.startswith(
                    "supabase:"
                ):

                    old_thumbnail_path = old_thumbnail.replace(
                        "supabase:",
                        "",
                        1
                    ).lstrip("/")

                    try:

                        supabase.storage.from_(
                            "product-images"
                        ).remove([
                            old_thumbnail_path
                        ])

                    except Exception as e:

                        print(
                            "OLD THUMBNAIL DELETE ERROR:",
                            e
                        )

                # SAVE NEW THUMBNAIL PATH

                setattr(
                    product,
                    field_name,
                    "supabase:" + thumbnail_storage_path
                )

        # UPDATE ZIP FILE

        if product_file and product_file.filename:

            product_extension = os.path.splitext(
                product_file.filename
            )[1].lower()

            if product_extension != ".zip":

                return render_template(
                    "edit_product.html",
                    product=product,
                    error="Invalid digital product file. ZIP files only."
                )

            safe_id = uuid.uuid4().hex

            product_filename = (
                safe_id + ".zip"
            )

            product_storage_path = (
                "products/" + product_filename
            )

            try:

                upload_to_supabase_storage(
                    product_file,
                    "product-files",
                    product_storage_path,
                    "application/zip"
                )

            except Exception as e:

                print(
                    "SUPABASE ZIP UPLOAD ERROR:",
                    repr(e)
                )

                return render_template(
                    "edit_product.html",
                    product=product,
                    error="Digital product upload failed. Please try again."
                )

            # DELETE OLD SUPABASE ZIP

            if product.product_file and product.product_file.startswith(
                "supabase:"
            ):

                old_product_path = product.product_file.replace(
                    "supabase:",
                    "",
                    1
                ).lstrip("/")

                try:

                    supabase.storage.from_(
                        "product-files"
                    ).remove([
                        old_product_path
                    ])

                except Exception as e:

                    print(
                        "OLD SUPABASE ZIP DELETE ERROR:",
                        e
                    )

            # DELETE OLD LOCAL ZIP

            elif product.product_file:

                old_product_path = os.path.join(
                    app.root_path,
                    "downloads",
                    "products",
                    os.path.basename(
                        product.product_file
                    )
                )

                if os.path.isfile(old_product_path):

                    os.remove(old_product_path)

            product.product_file = (
                "supabase:" + product_storage_path
            )

        # SAVE DATABASE CHANGES

        db.session.commit()

        return redirect(
            url_for("admin")
        )

    return render_template(
        "edit_product.html",
        product=product
    )

@app.route("/admin/products/delete/<int:product_id>", methods=["POST"])
def delete_product(product_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    product = Product.query.get_or_404(product_id)

    # CHECK IF PRODUCT HAS ORDER HISTORY

    order_exists = Order.query.filter(
        Order.product_name == product.product_name
    ).first()

    # CHECK IF PRODUCT HAS DOWNLOAD HISTORY

    download_exists = Download.query.filter_by(
        product_id=product.id
    ).first()

    # PROTECT PRODUCT WITH HISTORY

    if order_exists or download_exists:

        product.active = False

        db.session.commit()

        return """
        <div style="
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 60px 20px;
        ">

            <h2>🔒 Product Protected</h2>

            <p>
                This product has existing order or download history.
            </p>

            <p>
                The product was <strong>HIDDEN</strong> instead of
                permanently deleted.
            </p>

            <br>

            <a
                href="/admin"
                style="
                    display: inline-block;
                    padding: 12px 20px;
                    background: #111827;
                    color: white;
                    text-decoration: none;
                    border-radius: 7px;
                "
            >
                ← Back to Admin
            </a>

        </div>
        """

    # DELETE PREVIEW IMAGE

    if product.preview_image:

        image_path = os.path.join(
            app.root_path,
            "static",
            product.preview_image
        )

        if os.path.isfile(image_path):
            os.remove(image_path)

    # DELETE DIGITAL ZIP

    if product.product_file:

        product_folder = os.path.join(
            app.root_path,
            "downloads",
            "products"
        )

        product_file_path = os.path.join(
            product_folder,
            os.path.basename(product.product_file)
        )

        if os.path.isfile(product_file_path):
            os.remove(product_file_path)

    # DELETE PRODUCT FROM DATABASE

    db.session.delete(product)

    db.session.commit()

    return redirect(url_for("admin"))

# =========================
# CHANGE ADMIN PASSWORD
# =========================

@app.route(
    "/admin/change-password",
    methods=["POST"]
)
def change_password():

    if not session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for("admin_login")
        )


    current_password = request.form.get(
        "current_password",
        ""
    )

    new_password = request.form.get(
        "new_password",
        ""
    )

    confirm_password = request.form.get(
        "confirm_password",
        ""
    )


    # Find logged-in admin

    admin_user = AdminUser.query.get(
        session.get("admin_user_id")
    )


    if not admin_user:

        session.clear()

        return redirect(
            url_for("admin_login")
        )


    # Check current password

    if not check_password_hash(
        admin_user.password_hash,
        current_password
    ):

        return redirect(
            url_for(
                "admin",
                password_error="Current password is incorrect."
            )
        )


    # Minimum password length

    if len(new_password) < 8:

        return redirect(
            url_for(
                "admin",
                password_error="New password must be at least 8 characters."
            )
        )


    # Confirm password

    if new_password != confirm_password:

        return redirect(
            url_for(
                "admin",
                password_error="New passwords do not match."
            )
        )


    # Don't allow same password

    if check_password_hash(
        admin_user.password_hash,
        new_password
    ):

        return redirect(
            url_for(
                "admin",
                password_error="New password must be different from the current password."
            )
        )


    # Save new password securely

    admin_user.password_hash = (
        generate_password_hash(
            new_password
        )
    )


    db.session.commit()


    return redirect(
        url_for(
            "admin",
            password_success="Password changed successfully."
        )
    )


# =========================
# ADMIN LOGOUT
# =========================

@app.route(
    "/admin/logout"
)
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# =========================
# RUN APPLICATION
# =========================

if __name__ == "__main__":

    app.run(
        debug=True
    )