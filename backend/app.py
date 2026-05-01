import csv
import os
import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from functools import wraps
from urllib.parse import quote_plus

import bcrypt
from dotenv import load_dotenv
import jwt
from email_validator import EmailNotValidError, validate_email
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from sqlalchemy import create_engine, func, or_, text

from .bill_util import write_order_bill
from .models import Book, BookOrder, OrderLine, OrderLineType, PaymentStatus, Role, User, db


def _mysql_reset_tables():
    drops = ("bs_order_lines", "bs_book_orders", "bs_books", "bs_users")
    with db.engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in drops:
            conn.execute(text(f"DROP TABLE IF EXISTS `{t}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        conn.commit()


def _mysql_safe_database_name(raw):
    name = (raw or "bookstore").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", name):
        raise ValueError("MYSQL_DATABASE must be 1–64 chars: letters, digits, underscore only")
    return name


def _ensure_mysql_database_exists():
    if os.environ.get("BOOKSTORE_USE_SQLITE") == "1":
        return
    if os.environ.get("DATABASE_URL"):
        return
    user = (os.environ.get("MYSQL_USER") or "root").strip()
    password = (os.environ.get("MYSQL_PASSWORD") or "").strip()
    host = (os.environ.get("MYSQL_HOST") or "127.0.0.1").strip()
    port = (os.environ.get("MYSQL_PORT") or "3306").strip()
    database = _mysql_safe_database_name(os.environ.get("MYSQL_DATABASE"))
    user_enc = quote_plus(user)
    pass_enc = quote_plus(password)
    auth = f"{user_enc}:{pass_enc}@" if password else f"{user_enc}:@"
    admin_uri = f"mysql+pymysql://{auth}{host}:{port}/?charset=utf8mb4"
    engine = create_engine(admin_uri, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
            conn.commit()
    finally:
        engine.dispose()


def _mysql_uri_from_env():
    user = (os.environ.get("MYSQL_USER") or "root").strip()
    password = (os.environ.get("MYSQL_PASSWORD") or "").strip()
    host = (os.environ.get("MYSQL_HOST") or "127.0.0.1").strip()
    port = (os.environ.get("MYSQL_PORT") or "3306").strip()
    database = _mysql_safe_database_name(os.environ.get("MYSQL_DATABASE"))
    user_enc = quote_plus(user)
    pass_enc = quote_plus(password)
    auth = f"{user_enc}:{pass_enc}@" if password else f"{user_enc}:@"
    return f"mysql+pymysql://{auth}{host}:{port}/{database}?charset=utf8mb4"


def _execute_sql_seed_file(abs_path):
    raw = open(abs_path, encoding="utf-8").read()
    for chunk in raw.split(";"):
        lines = [ln for ln in chunk.splitlines() if ln.strip() and not ln.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if not stmt:
            continue
        db.session.execute(text(stmt))
    db.session.commit()


def _seed_books_from_csv(abs_path):
    with open(abs_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("title") or "").strip()
            if not title:
                continue
            if Book.query.filter_by(title=title).first():
                continue
            ra_raw = (row.get("rental_available") or "1").strip().lower()
            rental_ok = ra_raw in ("1", "true", "yes", "")
            db.session.add(
                Book(
                    title=title,
                    author=(row.get("author") or "").strip(),
                    price_buy=Decimal(str(row.get("price_buy") or "0")),
                    price_rent=Decimal(str(row.get("price_rent") or "0")),
                    rental_available=rental_ok,
                )
            )
    db.session.commit()


def create_app():
    _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    load_dotenv(os.path.join(_project_root, ".env"))
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("BOOKSTORE_SECRET", "dev-change-me-in-production-32chars!!")
    if os.environ.get("BOOKSTORE_USE_SQLITE") == "1":
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(os.getcwd(), "bookstore.db")
    elif os.environ.get("DATABASE_URL"):
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    else:
        _ensure_mysql_database_exists()
        app.config["SQLALCHEMY_DATABASE_URI"] = _mysql_uri_from_env()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_EXP_HOURS"] = int(os.environ.get("JWT_EXP_HOURS", "24"))
    app.config["BILLS_DIR"] = os.environ.get("BILLS_DIR", os.path.join(os.getcwd(), "bills"))

    db.init_app(app)
    CORS(app)

    def hash_pw(pw):
        return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def check_pw(pw, h):
        return bcrypt.checkpw(pw.encode("utf-8"), h.encode("utf-8"))

    def make_token(user):
        exp = datetime.now(timezone.utc) + timedelta(hours=app.config["JWT_EXP_HOURS"])
        return jwt.encode(
            {"sub": user.username, "role": user.role.value, "exp": exp},
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )

    def require_auth(*roles):
        def deco(fn):
            @wraps(fn)
            def inner(*args, **kwargs):
                h = request.headers.get("Authorization", "")
                if not h.startswith("Bearer "):
                    return jsonify({"error": "Unauthorized"}), 401
                token = h[7:]
                try:
                    payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
                except jwt.PyJWTError:
                    return jsonify({"error": "Unauthorized"}), 401
                if roles and payload.get("role") not in roles:
                    return jsonify({"error": "Forbidden"}), 403
                g.username = payload["sub"]
                g.role = payload["role"]
                return fn(*args, **kwargs)

            return inner

        return deco

    def _auth_response(u):
        return {
            "token": make_token(u),
            "role": u.role.value,
            "username": u.username,
            "firstName": u.first_name or "",
            "lastName": u.last_name or "",
        }

    @app.post("/api/auth/register")
    def register():
        data = request.get_json(force=True, silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        email = (data.get("email") or "").strip()
        first_name = (data.get("firstName") or "").strip()
        last_name = (data.get("lastName") or "").strip()
        if len(username) < 3 or len(password) < 8:
            return jsonify({"error": "Invalid credentials format"}), 400
        if len(first_name) < 1 or len(last_name) < 1:
            return jsonify({"error": "First and last name are required"}), 400
        try:
            validate_email(email, check_deliverability=False)
        except EmailNotValidError:
            return jsonify({"error": "Invalid email"}), 400
        if User.query.filter_by(username=username).first():
            return jsonify({"error": "Username taken"}), 409
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email in use"}), 409
        u = User(
            username=username,
            password_hash=hash_pw(password),
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=Role.CUSTOMER,
        )
        db.session.add(u)
        db.session.commit()
        return jsonify(_auth_response(u))

    @app.post("/api/auth/login")
    def login():
        data = request.get_json(force=True, silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        u = User.query.filter_by(username=username).first()
        if not u or not check_pw(password, u.password_hash):
            return jsonify({"error": "Invalid credentials"}), 401
        return jsonify(_auth_response(u))

    @app.get("/api/books/search")
    @require_auth("CUSTOMER", "MANAGER")
    def search_books():
        q = (request.args.get("q") or "").strip()
        if not q:
            books = Book.query.order_by(Book.title).all()
        else:
            like = f"%{q}%"
            books = Book.query.filter(or_(Book.title.like(like), Book.author.like(like))).order_by(Book.title).all()
        return jsonify(
            [
                {
                    "id": b.id,
                    "title": b.title,
                    "author": b.author,
                    "priceBuy": str(b.price_buy),
                    "priceRent": str(b.price_rent),
                    "rentalAvailable": b.rental_available,
                }
                for b in books
            ]
        )

    @app.post("/api/orders")
    @require_auth("CUSTOMER")
    def place_order():
        data = request.get_json(force=True, silent=True) or {}
        items = data.get("items") or []
        if not items:
            return jsonify({"error": "No items"}), 400
        u = User.query.filter_by(username=g.username).first()
        if not u or u.role != Role.CUSTOMER:
            return jsonify({"error": "Forbidden"}), 403
        order = BookOrder(customer=u, payment_status=PaymentStatus.PENDING, total_amount=Decimal("0"))
        db.session.add(order)
        db.session.flush()
        total = Decimal("0")
        for it in items:
            book_id = it.get("bookId")
            typ = it.get("type")
            qty = int(it.get("quantity") or 1)
            if qty < 1:
                db.session.rollback()
                return jsonify({"error": "Invalid quantity"}), 400
            b = Book.query.get(book_id)
            if not b:
                db.session.rollback()
                return jsonify({"error": "Book not found"}), 404
            if typ == "BUY":
                unit = Decimal(str(b.price_buy))
                lt = OrderLineType.BUY
            elif typ == "RENT":
                if not b.rental_available:
                    db.session.rollback()
                    return jsonify({"error": f"Rental not available: {b.title}"}), 400
                unit = Decimal(str(b.price_rent))
                lt = OrderLineType.RENT
            else:
                db.session.rollback()
                return jsonify({"error": "Invalid line type"}), 400
            line = OrderLine(order=order, book=b, line_type=lt, unit_price=unit, quantity=qty)
            db.session.add(line)
            total += unit * qty
        order.total_amount = total
        db.session.commit()
        db.session.refresh(order)
        for line in order.lines:
            db.session.refresh(line.book)
        path = write_order_bill(order, app.config["BILLS_DIR"])
        order.bill_html_path = path
        db.session.commit()
        return jsonify(order_to_json(order))

    @app.get("/api/orders/me")
    @require_auth("CUSTOMER")
    def my_orders():
        u = User.query.filter_by(username=g.username).first()
        orders = (
            BookOrder.query.filter_by(user_id=u.id).order_by(BookOrder.created_at.desc()).all()
        )
        for o in orders:
            _ = o.lines
            for ln in o.lines:
                _ = ln.book
        return jsonify([order_to_json(o) for o in orders])

    @app.post("/api/manager/books")
    @require_auth("MANAGER")
    def manager_create_book():
        data = request.get_json(force=True, silent=True) or {}
        title = (data.get("title") or "").strip()
        author = (data.get("author") or "").strip()
        price_buy = Decimal(str(data.get("priceBuy") or "0"))
        price_rent = Decimal(str(data.get("priceRent") or "0"))
        rental_available = bool(data.get("rentalAvailable", True))
        if not title or not author or price_buy <= 0 or price_rent <= 0:
            return jsonify({"error": "Invalid book"}), 400
        existing = (
            Book.query.filter(
                func.lower(Book.title) == title.lower(),
                func.lower(Book.author) == author.lower(),
            ).first()
        )
        if existing:
            existing.price_buy = price_buy
            existing.price_rent = price_rent
            existing.rental_available = rental_available
            db.session.commit()
            return jsonify(book_to_json(existing))
        b = Book(
            title=title,
            author=author,
            price_buy=price_buy,
            price_rent=price_rent,
            rental_available=rental_available,
        )
        db.session.add(b)
        db.session.commit()
        return jsonify(book_to_json(b))

    @app.put("/api/manager/books/<int:book_id>")
    @require_auth("MANAGER")
    def manager_update_book(book_id):
        b = Book.query.get(book_id)
        if not b:
            return jsonify({"error": "Not found"}), 404
        data = request.get_json(force=True, silent=True) or {}
        if "title" in data:
            b.title = data["title"]
        if "author" in data:
            b.author = data["author"]
        if "priceBuy" in data:
            b.price_buy = Decimal(str(data["priceBuy"]))
        if "priceRent" in data:
            b.price_rent = Decimal(str(data["priceRent"]))
        if "rentalAvailable" in data:
            b.rental_available = bool(data["rentalAvailable"])
        if not b.title or not b.author or b.price_buy <= 0 or b.price_rent <= 0:
            return jsonify({"error": "Invalid book"}), 400
        db.session.commit()
        return jsonify(book_to_json(b))

    @app.get("/api/manager/orders")
    @require_auth("MANAGER")
    def manager_orders():
        orders = BookOrder.query.order_by(BookOrder.created_at.desc()).all()
        for o in orders:
            _ = o.customer
            for ln in o.lines:
                _ = ln.book
        return jsonify([order_to_json(o) for o in orders])

    @app.patch("/api/manager/orders/<int:order_id>/payment")
    @require_auth("MANAGER")
    def manager_payment(order_id):
        o = BookOrder.query.get(order_id)
        if not o:
            return jsonify({"error": "Not found"}), 404
        data = request.get_json(force=True, silent=True) or {}
        st = data.get("status")
        if st == "PAID":
            o.payment_status = PaymentStatus.PAID
        elif st == "PENDING":
            o.payment_status = PaymentStatus.PENDING
        else:
            return jsonify({"error": "Invalid status"}), 400
        db.session.commit()
        for ln in o.lines:
            _ = ln.book
        return jsonify(order_to_json(o))

    def book_to_json(b):
        return {
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "priceBuy": str(b.price_buy),
            "priceRent": str(b.price_rent),
            "rentalAvailable": b.rental_available,
        }

    def order_to_json(o):
        lines = []
        for ln in o.lines:
            unit = Decimal(str(ln.unit_price))
            lines.append(
                {
                    "bookId": ln.book_id,
                    "title": ln.book.title,
                    "author": ln.book.author,
                    "type": ln.line_type.value,
                    "quantity": ln.quantity,
                    "unitPrice": str(ln.unit_price),
                    "lineTotal": str(unit * ln.quantity),
                }
            )
        return {
            "orderId": o.id,
            "customerUsername": o.customer.username if o.customer else None,
            "paymentStatus": o.payment_status.value,
            "totalAmount": str(o.total_amount),
            "createdAt": o.created_at.isoformat() if o.created_at else None,
            "billPath": o.bill_html_path,
            "lines": lines,
        }

    def seed():
        uri = app.config["SQLALCHEMY_DATABASE_URI"]
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if uri.startswith("mysql"):
            staff_sql = os.path.join(root, "sql", "seed_staff.sql")
            if os.path.isfile(staff_sql):
                _execute_sql_seed_file(staff_sql)
        else:
            if not User.query.filter_by(username="manager").first():
                db.session.add(
                    User(
                        username="manager",
                        password_hash=hash_pw("managerpass"),
                        email="manager@bookstore.local",
                        first_name="Store",
                        last_name="Manager",
                        role=Role.MANAGER,
                    )
                )
            db.session.commit()
        books_csv = os.path.join(root, "sql", "books.csv")
        if os.path.isfile(books_csv):
            _seed_books_from_csv(books_csv)

    with app.app_context():
        reset = (os.environ.get("BOOKSTORE_RESET_SCHEMA") or "").strip().lower()
        uri = app.config["SQLALCHEMY_DATABASE_URI"]
        mysql = "mysql" in uri
        if reset in ("1", "true", "yes"):
            if mysql:
                _mysql_reset_tables()
            else:
                db.drop_all()
        db.create_all()
        seed()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
