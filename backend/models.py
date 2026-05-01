import enum
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Role(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    MANAGER = "MANAGER"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"


class OrderLineType(str, enum.Enum):
    BUY = "BUY"
    RENT = "RENT"


class User(db.Model):
    __tablename__ = "bs_users"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(128), nullable=False, default="")
    last_name = db.Column(db.String(128), nullable=False, default="")
    role = db.Column(db.Enum(Role), nullable=False)

    orders = db.relationship(
        "BookOrder",
        back_populates="customer",
        primaryjoin="User.id == BookOrder.user_id",
        foreign_keys="BookOrder.user_id",
    )


class Book(db.Model):
    __tablename__ = "bs_books"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(512), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    price_buy = db.Column(db.Numeric(12, 2), nullable=False)
    price_rent = db.Column(db.Numeric(12, 2), nullable=False)
    rental_available = db.Column(db.Boolean, nullable=False, default=True)


class BookOrder(db.Model):
    __tablename__ = "bs_book_orders"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False)
    payment_status = db.Column(db.Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    total_amount = db.Column(db.Numeric(14, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    bill_html_path = db.Column(db.String(1024))

    customer = db.relationship(
        "User",
        back_populates="orders",
        primaryjoin="BookOrder.user_id == User.id",
        foreign_keys="BookOrder.user_id",
    )
    lines = db.relationship(
        "OrderLine",
        back_populates="order",
        cascade="all, delete-orphan",
        primaryjoin="BookOrder.id == OrderLine.order_id",
        foreign_keys="OrderLine.order_id",
    )


class OrderLine(db.Model):
    __tablename__ = "bs_order_lines"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, nullable=False)
    book_id = db.Column(db.Integer, nullable=False)
    line_type = db.Column(db.Enum(OrderLineType), nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    order = db.relationship(
        "BookOrder",
        back_populates="lines",
        primaryjoin="OrderLine.order_id == BookOrder.id",
        foreign_keys="OrderLine.order_id",
    )
    book = db.relationship(
        "Book",
        primaryjoin="OrderLine.book_id == Book.id",
        foreign_keys="OrderLine.book_id",
    )
