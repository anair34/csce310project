import html
import os
import sys
from decimal import Decimal

import requests
from styles import APP_QSS
from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QIntValidator,
    QPalette,
    QTextDocument,
)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

API_BASE = os.environ.get("BOOKSTORE_API", "http://127.0.0.1:5000")

# Uniform table row height; vertical header uses Fixed so rows cannot be drag-resized.
TABLE_ROW_HEIGHT_PX = 42


def _money(value) -> str:
    try:
        return f"${Decimal(str(value)):.2f}"
    except Exception:
        return f"${value}"


def _parse_money_field(text: str) -> float:
    s = (text or "").strip().replace(",", "")
    if s.startswith("$"):
        s = s[1:].strip()
    if not s:
        return 0.0
    return float(s)


def format_order_html(o, show_customer=False):
    if not o:
        return "<p style='color:#64748b;margin:8px'>Select an order to see line items.</p>"
    lines = o.get("lines") or []
    rows = []
    for ln in lines:
        rows.append(
            "<tr>"
            f"<td style='padding:10px 12px;border-bottom:1px solid #e2e8f0;color:#0f172a'>{html.escape(ln.get('title',''))}</td>"
            f"<td style='padding:10px 8px;border-bottom:1px solid #e2e8f0;color:#64748b'>{html.escape(ln.get('author',''))}</td>"
            f"<td style='padding:10px 8px;border-bottom:1px solid #e2e8f0;text-align:center'>"
            f"<span style='padding:3px 10px;border-radius:6px;background:#e2e8f0;color:#334155;font-size:11px;font-weight:600'>"
            f"{html.escape(ln.get('type',''))}</span></td>"
            f"<td style='padding:10px 8px;border-bottom:1px solid #e2e8f0;text-align:right;color:#0f172a'>{ln.get('quantity','')}</td>"
            f"<td style='padding:10px 8px;border-bottom:1px solid #e2e8f0;text-align:right;color:#64748b'>"
            f"{html.escape(_money(ln.get('unitPrice','')))}</td>"
            f"<td style='padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:right;font-weight:800;color:#334155'>"
            f"{html.escape(_money(ln.get('lineTotal','')))}</td>"
            "</tr>"
        )
    pay = o.get("paymentStatus", "")
    badge_bg = "#dbeafe" if pay == "PAID" else "#fef3c7"
    badge_fg = "#1d4ed8" if pay == "PAID" else "#b45309"
    badge_bd = "#bfdbfe" if pay == "PAID" else "#fde68a"
    cust = ""
    if show_customer:
        c = o.get("customerUsername") or "—"
        cust = f"<span style='color:#64748b'>Customer</span> <b style='color:#0f172a'>{html.escape(str(c))}</b> · "
    when = html.escape(str(o.get("createdAt") or "")[:19])
    return (
        "<div style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#fefdfb'>"
        f"<p style='margin:0 0 6px 0'>"
        f"<span style='font-size:20px;font-weight:800;color:#0f172a'>Order #{o.get('orderId','')}</span> "
        f"<span style='margin-left:14px;padding:6px 14px;border-radius:999px;background:{badge_bg};color:{badge_fg};"
        f"font-weight:700;font-size:12px;border:1px solid {badge_bd}'>{html.escape(pay)}</span></p>"
        f"<p style='margin:0 0 16px 0;font-size:13px'>{cust}"
        f"<span style='color:#64748b'>Placed</span> <span style='color:#0f172a;font-weight:500'>{when}</span></p>"
        f"<p style='margin:0 0 12px 0;font-size:22px;font-weight:800;color:#334155'>Total "
        f"<span style='color:#0f172a'>{html.escape(_money(o.get('totalAmount','')))}</span></p>"
        "<table width='100%' cellspacing='0' style='font-size:13px;border-collapse:collapse;margin-top:12px'>"
        "<tr style='background:#475569;color:#f8fafc;font-size:11px;text-transform:uppercase;letter-spacing:0.5px'>"
        "<th align='left' style='padding:10px 12px'>Title</th>"
        "<th align='left' style='padding:10px 8px'>Author</th>"
        "<th align='center' style='padding:10px 8px'>Type</th>"
        "<th align='right' style='padding:10px 8px'>Qty</th>"
        "<th align='right' style='padding:10px 8px'>Unit</th>"
        "<th align='right' style='padding:10px 12px'>Line total</th></tr>"
        f"{''.join(rows)}"
        "</table></div>"
    )


class Api:
    def __init__(self):
        self.token = None

    def headers(self):
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def register(self, username, password, email, first_name, last_name):
        return requests.post(
            f"{API_BASE}/api/auth/register",
            json={
                "username": username,
                "password": password,
                "email": email,
                "firstName": first_name,
                "lastName": last_name,
            },
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

    def login(self, username, password):
        return requests.post(
            f"{API_BASE}/api/auth/login",
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

    def search(self, q):
        return requests.get(
            f"{API_BASE}/api/books/search",
            params={"q": q},
            headers=self.headers(),
            timeout=30,
        )

    def place_order(self, items):
        return requests.post(
            f"{API_BASE}/api/orders",
            json={"items": items},
            headers=self.headers(),
            timeout=60,
        )

    def my_orders(self):
        return requests.get(f"{API_BASE}/api/orders/me", headers=self.headers(), timeout=30)

    def manager_orders(self):
        return requests.get(f"{API_BASE}/api/manager/orders", headers=self.headers(), timeout=30)

    def manager_payment(self, order_id, status):
        return requests.patch(
            f"{API_BASE}/api/manager/orders/{order_id}/payment",
            json={"status": status},
            headers=self.headers(),
            timeout=30,
        )

    def manager_create_book(self, payload):
        return requests.post(
            f"{API_BASE}/api/manager/books",
            json=payload,
            headers=self.headers(),
            timeout=30,
        )

    def manager_update_book(self, book_id, payload):
        return requests.put(
            f"{API_BASE}/api/manager/books/{book_id}",
            json=payload,
            headers=self.headers(),
            timeout=30,
        )


class ReqThread(QThread):
    ok = Signal(object)
    err = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.ok.emit(self._fn())
        except Exception as e:
            self.err.emit(str(e))


class BookstoreWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bookstore")
        self.resize(1100, 720)
        self.setMinimumSize(960, 600)
        self.api = Api()
        self.role = None
        self.username = None
        self.first_name = ""
        self.last_name = ""
        self._hist_timer = QTimer(self)
        self._hist_timer.setInterval(5000)
        self.cart = []
        self._book_rows = {}
        self._mgr_books = {}
        self._hist_orders_cache = []
        self._mgr_orders_cache = []

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self._login_page = self._make_login_page()
        self._customer_page = self._make_customer_page()
        self._manager_page = self._make_manager_page()

        self.stack.addWidget(self._login_page)
        self.stack.addWidget(self._customer_page)
        self.stack.addWidget(self._manager_page)

        self.stack.setCurrentWidget(self._login_page)

    def _run(self, fn, on_ok, on_err=None):
        t = ReqThread(fn)

        def _ok(x):
            on_ok(x)
            t.deleteLater()

        def _err(e):
            if on_err:
                on_err(e)
            else:
                QMessageBox.critical(self, "Error", e)
            t.deleteLater()

        t.ok.connect(_ok)
        t.err.connect(_err)
        t.start()

    def _apply_table_selection(self, table):
        pal = table.palette()
        pal.setColor(QPalette.ColorRole.Highlight, QColor("#e2e8f0"))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#0f172a"))
        table.setPalette(pal)
        table.setFocusPolicy(Qt.StrongFocus)

    def _apply_header_alignments(self, table, *h_aligns):
        for col, ha in enumerate(h_aligns):
            hi = table.horizontalHeaderItem(col)
            if hi is not None:
                hi.setTextAlignment(ha | Qt.AlignVCenter)

    def _mgr_current_order(self):
        r = self._ord_table.currentRow()
        if r < 0 or r >= len(self._mgr_orders_cache):
            return None
        return self._mgr_orders_cache[r]

    def _mgr_open_bill(self):
        o = self._mgr_current_order()
        if not o:
            QMessageBox.information(self, "Bill", "Select an order in the table first.")
            return
        path = (o.get("billPath") or "").strip()
        if not path:
            QMessageBox.warning(self, "Bill", "No saved bill file for this order.")
            return
        if not os.path.isfile(path):
            QMessageBox.warning(
                self,
                "Bill",
                f"The bill file is missing on this computer:\n{path}\n\n"
                "The server saves bills under BILLS_DIR; open the app on the same machine as the API, or copy the file.",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))

    def _mgr_print_bill(self):
        o = self._mgr_current_order()
        if not o:
            QMessageBox.information(self, "Bill", "Select an order in the table first.")
            return
        path = (o.get("billPath") or "").strip()
        if not path or not os.path.isfile(path):
            QMessageBox.warning(
                self,
                "Bill",
                "No readable bill file for this order. Use Open Bill to check the path.",
            )
            return
        with open(path, encoding="utf-8") as f:
            html_src = f.read()
        doc = QTextDocument()
        doc.setHtml(html_src)
        printer = QPrinter()
        dlg = QPrintDialog(printer, self)
        if dlg.exec() == QDialog.Accepted:
            doc.print_(printer)

    def _lock_table_row_sizes(self, table, row_height=TABLE_ROW_HEIGHT_PX):
        vh = table.verticalHeader()
        vh.setFixedWidth(52)
        vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vh.setMinimumSectionSize(row_height)
        vh.setDefaultSectionSize(row_height)
        table.setWordWrap(False)

    def _make_login_page(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(40, 40, 40, 40)
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(40, 36, 40, 40)
        t1 = QLabel("Aditya's Bookstore")
        t1.setObjectName("title")
        t2 = QLabel("Sign in or create an account to get started.")
        t2.setObjectName("sub")
        lay.addWidget(t1)
        lay.addWidget(t2)
        lay.addSpacing(20)
        form = QVBoxLayout()
        lay.addLayout(form)
        self._l_user = QLineEdit()
        self._l_user.setPlaceholderText("Username")
        self._l_pass = QLineEdit()
        self._l_pass.setPlaceholderText("Password")
        self._l_pass.setEchoMode(QLineEdit.Password)
        form.addWidget(QLabel("Username"))
        form.addWidget(self._l_user)
        form.addWidget(QLabel("Password"))
        form.addWidget(self._l_pass)
        row = QHBoxLayout()
        b_in = QPushButton("Sign in")
        b_reg = QPushButton("Create account")
        b_in.setObjectName("ghost")
        b_reg.setObjectName("ghost")
        row.addWidget(b_in)
        row.addWidget(b_reg)
        row.addStretch()
        lay.addLayout(row)
        lay.addStretch()
        outer.addStretch()
        outer.addWidget(card)
        outer.addStretch()

        def do_login():
            u = self._l_user.text().strip()
            p = self._l_pass.text()
            if not u or not p:
                QMessageBox.warning(self, "Missing", "Enter username and password.")
                return

            def on_ok(r):
                if r.status_code != 200:
                    try:
                        msg = r.json().get("error", r.text)
                    except Exception:
                        msg = r.text
                    QMessageBox.critical(self, "Login failed", msg)
                    return
                data = r.json()
                self.api.token = data["token"]
                self.role = data["role"]
                self.username = data["username"]
                self.first_name = (data.get("firstName") or "").strip()
                self.last_name = (data.get("lastName") or "").strip()
                if self.role == "MANAGER":
                    self._show_manager()
                else:
                    self._show_customer()

            self._run(lambda: self.api.login(u, p), on_ok)

        b_in.clicked.connect(do_login)
        b_reg.clicked.connect(self._open_register)
        return w

    def _open_register(self):
        d = QDialog(self)
        d.setWindowTitle("Create account")
        d.setMinimumWidth(440)
        d.resize(480, 520)

        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(d)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.addWidget(card)

        v = QVBoxLayout(card)
        v.setContentsMargins(40, 36, 40, 36)

        head = QLabel("Create an Account")
        head.setObjectName("title")
        v.addWidget(head)
        v.addSpacing(16)

        ef, el = QLineEdit(), QLineEdit()
        eu, ee, ep = QLineEdit(), QLineEdit(), QLineEdit()
        ep.setEchoMode(QLineEdit.Password)
        ef.setPlaceholderText("Given name")
        el.setPlaceholderText("Family name")
        eu.setPlaceholderText("Choose a username")
        ee.setPlaceholderText("you@example.com")
        ep.setPlaceholderText("At least 8 characters")
        for w in (ef, el, eu, ee, ep):
            w.setMinimumHeight(40)
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        for lab, widget in (
            ("First name", ef),
            ("Last name", el),
            ("Username", eu),
            ("Email", ee),
            ("Password (8+ characters)", ep),
        ):
            v.addWidget(QLabel(lab))
            v.addWidget(widget)
            v.addSpacing(4)

        v.addSpacing(12)
        br = QHBoxLayout()
        b_ok = QPushButton("Register")
        b_cancel = QPushButton("Cancel")
        b_ok.setObjectName("ghost")
        b_cancel.setObjectName("ghost")
        br.addWidget(b_ok)
        br.addWidget(b_cancel)
        br.addStretch()
        v.addLayout(br)

        def submit():
            fn = ef.text().strip()
            ln = el.text().strip()
            if not fn or not ln:
                QMessageBox.warning(d, "Name", "Enter first and last name.")
                return
            if len(ep.text()) < 8:
                QMessageBox.warning(d, "Password", "Use at least 8 characters.")
                return

            def on_ok(r):
                if r.status_code != 200:
                    try:
                        msg = r.json().get("error", r.text)
                    except Exception:
                        msg = r.text
                    QMessageBox.critical(d, "Registration", msg)
                    return
                data = r.json()
                self.api.token = data["token"]
                self.role = data["role"]
                self.username = data["username"]
                self.first_name = (data.get("firstName") or "").strip()
                self.last_name = (data.get("lastName") or "").strip()
                d.accept()
                self._show_customer()

            self._run(
                lambda: self.api.register(
                    eu.text().strip(), ep.text(), ee.text().strip(), fn, ln
                ),
                on_ok,
            )

        b_ok.clicked.connect(submit)
        b_cancel.clicked.connect(d.reject)
        d.exec()

    def _dialog_pick_quantity(self, title: str, b: dict):
        """Same shell as Create account: padded outer, #card, title + form + buttons."""
        d = QDialog(self)
        d.setWindowTitle(title)
        d.setMinimumWidth(440)
        d.resize(480, 320)

        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(d)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.addWidget(card)

        v = QVBoxLayout(card)
        v.setContentsMargins(40, 36, 40, 36)

        head = QLabel(title)
        head.setObjectName("title")
        v.addWidget(head)
        v.addSpacing(10)

        auth = (b.get("author") or "").strip()
        book_line = f'"{b["title"]}"' + (f"\n{auth}" if auth else "")
        sub = QLabel(book_line)
        sub.setObjectName("sub")
        sub.setWordWrap(True)
        v.addWidget(sub)
        v.addSpacing(14)

        v.addWidget(QLabel("How many copies?"))
        qty_edit = QLineEdit()
        qty_edit.setPlaceholderText("1 to 99")
        qty_edit.setText("1")
        qty_edit.setValidator(QIntValidator(1, 99, d))
        qty_edit.setMinimumHeight(40)
        qty_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        v.addWidget(qty_edit)
        v.addSpacing(14)

        picked = {"n": None}

        br = QHBoxLayout()
        b_ok = QPushButton("Add to cart")
        b_cancel = QPushButton("Cancel")
        b_ok.setObjectName("ghost")
        b_cancel.setObjectName("ghost")
        br.addWidget(b_ok)
        br.addWidget(b_cancel)
        br.addStretch()
        v.addLayout(br)

        def submit():
            t = qty_edit.text().strip()
            if not t.isdigit():
                QMessageBox.warning(d, title, "Enter a whole number from 1 to 99.")
                return
            n = int(t)
            if n < 1 or n > 99:
                QMessageBox.warning(d, title, "Use a quantity from 1 to 99.")
                return
            picked["n"] = n
            d.accept()

        b_ok.clicked.connect(submit)
        b_cancel.clicked.connect(d.reject)
        qty_edit.returnPressed.connect(submit)

        if d.exec() != QDialog.Accepted:
            return None
        return picked["n"]

    def _logout(self):
        self._hist_timer.stop()
        self.api.token = None
        self.role = None
        self.username = None
        self.first_name = ""
        self.last_name = ""
        self.stack.setCurrentWidget(self._login_page)

    def _show_customer(self):
        self.cart = []
        self._cust_cart.clear()
        self.stack.setCurrentWidget(self._customer_page)
        display_name = f"{self.first_name} {self.last_name}".strip()
        if display_name:
            self._cust_title.setText(f"Welcome, {display_name}!")
        else:
            self._cust_title.setText("Welcome!")
        QTimer.singleShot(50, self._cust_do_search)
        QTimer.singleShot(100, self._cust_load_history)
        self._hist_timer.start()

    def _show_manager(self):
        self._hist_timer.stop()
        self.stack.setCurrentWidget(self._manager_page)
        QTimer.singleShot(50, self._mgr_load_orders)
        QTimer.singleShot(80, self._mgr_load_books)

    def _make_customer_page(self):
        w = QWidget()
        main = QVBoxLayout(w)
        main.setContentsMargins(32, 52, 32, 20)
        main.setSpacing(18)
        self._cust_title = QLabel()
        self._cust_title.setObjectName("title")
        self._cust_title.setAlignment(Qt.AlignCenter)
        main.addWidget(self._cust_title)

        tabs = QTabWidget()
        shop = QWidget()
        sl = QVBoxLayout(shop)
        sl.setSpacing(10)
        cat_lbl = QLabel("Catalog")
        cat_lbl.setObjectName("section")
        sl.addWidget(cat_lbl)
        cat_hint = QLabel(
            "Select a book from the catalog and add it to your cart."
        )
        cat_hint.setObjectName("hint")
        sl.addWidget(cat_hint)
        sh = QHBoxLayout()
        self._sq = QLineEdit()
        self._sq.setPlaceholderText("Search by title or author…")
        b_se = QPushButton("Search")
        b_all = QPushButton("Show all")
        b_se.setObjectName("ghost")
        b_all.setObjectName("ghost")
        sh.addWidget(QLabel("Search"))
        sh.addWidget(self._sq, 1)
        sh.addWidget(b_se)
        sh.addWidget(b_all)
        sl.addLayout(sh)
        sl.addSpacing(20)

        self._book_table = QTableWidget(0, 5)
        self._book_table.setHorizontalHeaderLabels(["Title", "Author", "Buy", "Rent", "Rent OK"])
        self._apply_header_alignments(
            self._book_table,
            Qt.AlignLeft,
            Qt.AlignLeft,
            Qt.AlignRight,
            Qt.AlignRight,
            Qt.AlignCenter,
        )
        _bh = self._book_table.horizontalHeader()
        _bh.setSectionResizeMode(0, QHeaderView.Stretch)
        _bh.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (2, 3, 4):
            _bh.setSectionResizeMode(col, QHeaderView.Fixed)
        self._book_table.setColumnWidth(2, 96)
        self._book_table.setColumnWidth(3, 96)
        self._book_table.setColumnWidth(4, 92)
        self._lock_table_row_sizes(self._book_table)
        self._book_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._book_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._book_table.setAlternatingRowColors(True)
        self._book_table.setShowGrid(False)
        self._apply_table_selection(self._book_table)
        sl.addWidget(self._book_table, 1)

        cart_lbl = QLabel("Your cart")
        cart_lbl.setObjectName("section")
        sl.addWidget(cart_lbl)
        cart_hint = QLabel(
            "You can either buy or rent a book. Prices are shown in the catalog."
        )
        cart_hint.setObjectName("hint")
        cart_hint.setWordWrap(True)
        sl.addWidget(cart_hint)
        self._cust_cart = QListWidget()
        self._cust_cart.setObjectName("cartList")
        self._cust_cart.setMinimumHeight(120)
        self._cust_cart.setMaximumHeight(220)
        sl.addWidget(self._cust_cart)
        cr = QHBoxLayout()
        b_buy = QPushButton("Buy")
        b_rent = QPushButton("Rent")
        b_rm = QPushButton("Remove Selected")
        b_clr = QPushButton("Clear Cart")
        b_go = QPushButton("Place Order")
        for _b in (b_buy, b_rent, b_rm, b_clr, b_go):
            _b.setObjectName("ghost")
        self._cust_sign_out = QPushButton("Sign out")
        self._cust_sign_out.setObjectName("ghost")
        self._cust_sign_out.clicked.connect(self._logout)
        cr.addWidget(b_buy)
        cr.addWidget(b_rent)
        cr.addWidget(b_rm)
        cr.addWidget(b_clr)
        cr.addWidget(b_go)
        cr.addStretch()
        cr.addWidget(self._cust_sign_out)
        sl.addLayout(cr)

        hist = QWidget()
        hl = QVBoxLayout(hist)
        hl.setSpacing(8)
        oh = QLabel("Order History")
        oh.setObjectName("section")
        hl.addWidget(oh)
        ohint = QLabel(
            "Select an order to view details and line items of past orders."
        )
        ohint.setObjectName("hint")
        hl.addWidget(ohint)
        hist_order_stack = QWidget()
        hist_order_lay = QVBoxLayout(hist_order_stack)
        hist_order_lay.setContentsMargins(0, 0, 0, 0)
        hist_order_lay.setSpacing(8)
        self._hist_table = QTableWidget(0, 4)
        self._hist_table.setHorizontalHeaderLabels(["Order #", "Status", "Total", "Placed"])
        self._apply_header_alignments(
            self._hist_table,
            Qt.AlignLeft,
            Qt.AlignLeft,
            Qt.AlignRight,
            Qt.AlignLeft,
        )
        _hh = self._hist_table.horizontalHeader()
        _hh.setSectionResizeMode(0, QHeaderView.Fixed)
        _hh.setSectionResizeMode(1, QHeaderView.Fixed)
        _hh.setSectionResizeMode(2, QHeaderView.Fixed)
        _hh.setSectionResizeMode(3, QHeaderView.Stretch)
        self._hist_table.setColumnWidth(0, 88)
        self._hist_table.setColumnWidth(1, 88)
        self._hist_table.setColumnWidth(2, 112)
        self._lock_table_row_sizes(self._hist_table)
        self._hist_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._hist_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._hist_table.setAlternatingRowColors(True)
        self._hist_table.setShowGrid(False)
        self._apply_table_selection(self._hist_table)
        self._hist_detail = QTextBrowser()
        self._hist_detail.setObjectName("orderDetail")
        self._hist_detail.setMinimumHeight(120)
        self._hist_detail.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._hist_detail.setHtml(format_order_html(None))
        hist_order_lay.addWidget(self._hist_table, 1)
        hist_order_lay.addWidget(self._hist_detail, 1)
        hl.addWidget(hist_order_stack, 1)

        def sync_hist_detail():
            r = self._hist_table.currentRow()
            if r < 0 or r >= len(self._hist_orders_cache):
                self._hist_detail.setHtml(format_order_html(None))
                return
            self._hist_detail.setHtml(format_order_html(self._hist_orders_cache[r], False))

        self._hist_table.itemSelectionChanged.connect(sync_hist_detail)
        hist_btns = QHBoxLayout()
        hist_btns.addStretch()
        b_hist_sign = QPushButton("Sign out")
        b_hist_sign.setObjectName("ghost")
        b_hist_sign.clicked.connect(self._logout)
        hist_btns.addWidget(b_hist_sign)
        hl.addLayout(hist_btns)

        tabs.addTab(shop, "Shop")
        tabs.addTab(hist, "My Orders")
        main.addWidget(tabs, 1)

        def refresh_books(rows):
            self._book_rows.clear()
            self._book_table.setRowCount(0)
            for b in rows:
                bid = b["id"]
                self._book_rows[bid] = b
                r = self._book_table.rowCount()
                self._book_table.insertRow(r)
                it0 = QTableWidgetItem(b["title"])
                it0.setData(Qt.UserRole, bid)
                it0.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                it0.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self._book_table.setItem(r, 0, it0)
                for col, val in enumerate(
                    [
                        b["author"],
                        _money(b["priceBuy"]),
                        _money(b["priceRent"]),
                        "Y" if b["rentalAvailable"] else "N",
                    ],
                    start=1,
                ):
                    it = QTableWidgetItem(val)
                    it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    if col in (2, 3):
                        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    elif col == 4:
                        it.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                    else:
                        it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self._book_table.setItem(r, col, it)
                self._book_table.setRowHeight(r, TABLE_ROW_HEIGHT_PX)

        def do_search():
            qv = self._sq.text().strip()

            def call():
                r = self.api.search(qv)
                r.raise_for_status()
                return r.json()

            self._run(call, refresh_books)

        def _cart_line_label(c):
            qty = int(c["qty"])
            unit = Decimal(str(c["unit"]))
            sub = unit * qty
            return (
                f'{c["title"]} — {c["type"]} ×{qty} @ {_money(c["unit"])} ea · {_money(sub)}'
            )

        def cart_refresh(prefer_row=None):
            prev = self._cust_cart.currentRow() if prefer_row is None else prefer_row
            self._cust_cart.blockSignals(True)
            self._cust_cart.clear()
            for c in self.cart:
                self._cust_cart.addItem(QListWidgetItem(_cart_line_label(c)))
            self._cust_cart.blockSignals(False)
            if not self.cart:
                self._cust_cart.clearSelection()
                return
            pick = 0 if prev < 0 else min(prev, len(self.cart) - 1)
            self._cust_cart.setCurrentRow(pick)

        def remove_cart_line():
            r = self._cust_cart.currentRow()
            if r < 0 or r >= len(self.cart):
                QMessageBox.information(self, "Cart", "Select a line in your cart to remove it.")
                return
            self.cart.pop(r)
            if not self.cart:
                cart_refresh(None)
                return
            cart_refresh(min(r, len(self.cart) - 1))

        def sel_book():
            r = self._book_table.currentRow()
            if r < 0:
                QMessageBox.information(self, "Select a book", "Choose a row in the catalog.")
                return None
            it = self._book_table.item(r, 0)
            if not it:
                return None
            bid = int(it.data(Qt.UserRole))
            return self._book_rows.get(bid)

        def add_buy():
            b = sel_book()
            if not b:
                return
            qty = self._dialog_pick_quantity("Buy", b)
            if qty is None or qty < 1:
                return
            self.cart.append(
                {
                    "bookId": b["id"],
                    "type": "BUY",
                    "qty": qty,
                    "title": b["title"],
                    "author": b.get("author") or "",
                    "unit": b["priceBuy"],
                }
            )
            cart_refresh(len(self.cart) - 1)

        def add_rent():
            b = sel_book()
            if not b:
                return
            if not b["rentalAvailable"]:
                QMessageBox.warning(self, "Unavailable", "Rental is not available for this title.")
                return
            qty = self._dialog_pick_quantity("Rent", b)
            if qty is None or qty < 1:
                return
            self.cart.append(
                {
                    "bookId": b["id"],
                    "type": "RENT",
                    "qty": qty,
                    "title": b["title"],
                    "author": b.get("author") or "",
                    "unit": b["priceRent"],
                }
            )
            cart_refresh(len(self.cart) - 1)

        def checkout():
            if not self.cart:
                QMessageBox.information(self, "Cart", "Add items first.")
                return
            items = [{"bookId": c["bookId"], "type": c["type"], "quantity": c["qty"]} for c in self.cart]

            def on_ok(r):
                if r.status_code != 200:
                    try:
                        msg = r.json().get("error", r.text)
                    except Exception:
                        msg = r.text
                    QMessageBox.critical(self, "Order", msg)
                    return
                data = r.json()
                self.cart.clear()
                cart_refresh(None)
                lines = "\n".join(
                    f'  • {ln["title"]} ({ln["type"]}) x{ln["quantity"]} = {_money(ln["lineTotal"])}'
                    for ln in data["lines"]
                )
                QMessageBox.information(
                    self,
                    "Order placed",
                    f"Order #{data['orderId']}\nTotal: {_money(data['totalAmount'])}\n\n{lines}\n\nBill saved:\n{data.get('billPath', '')}",
                )
                self._cust_load_history()

            self._run(lambda: self.api.place_order(items), on_ok)

        b_se.clicked.connect(do_search)
        b_all.clicked.connect(lambda: (self._sq.clear(), do_search()))
        b_buy.clicked.connect(add_buy)
        b_rent.clicked.connect(add_rent)
        b_rm.clicked.connect(remove_cart_line)
        b_clr.clicked.connect(lambda: (self.cart.clear(), cart_refresh(None)))
        b_go.clicked.connect(checkout)

        def load_history():
            def call():
                r = self.api.my_orders()
                r.raise_for_status()
                return r.json()

            def on_ok(rows):
                prev_id = None
                cur = self._hist_table.currentRow()
                if 0 <= cur < len(self._hist_orders_cache):
                    prev_id = self._hist_orders_cache[cur].get("orderId")
                self._hist_orders_cache = list(rows)
                self._hist_table.setRowCount(0)
                for o in rows:
                    r = self._hist_table.rowCount()
                    self._hist_table.insertRow(r)
                    c0 = QTableWidgetItem(str(o["orderId"]))
                    c0.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    c0.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self._hist_table.setItem(r, 0, c0)
                    st = o["paymentStatus"]
                    c1 = QTableWidgetItem(st)
                    c1.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    c1.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    if st == "PAID":
                        c1.setForeground(QBrush(QColor("#1d4ed8")))
                    else:
                        c1.setForeground(QBrush(QColor("#b45309")))
                    self._hist_table.setItem(r, 1, c1)
                    c2 = QTableWidgetItem(_money(o["totalAmount"]))
                    c2.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    c2.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self._hist_table.setItem(r, 2, c2)
                    c3 = QTableWidgetItem((o.get("createdAt") or "")[:19])
                    c3.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    c3.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self._hist_table.setItem(r, 3, c3)
                    self._hist_table.setRowHeight(r, TABLE_ROW_HEIGHT_PX)
                pick = 0
                if prev_id is not None and rows:
                    for i, o in enumerate(rows):
                        if o.get("orderId") == prev_id:
                            pick = i
                            break
                if rows:
                    self._hist_table.selectRow(pick)
                else:
                    self._hist_detail.setHtml(format_order_html(None))

            self._run(call, on_ok)

        self._cust_do_search = do_search
        self._cust_load_history = load_history
        self._hist_timer.timeout.connect(load_history)
        return w

    def _make_manager_page(self):
        w = QWidget()
        main = QVBoxLayout(w)
        main.setContentsMargins(32, 36, 32, 24)
        main.setSpacing(18)
        self._mgr_header = QLabel("Manager Console")
        self._mgr_header.setObjectName("title")
        self._mgr_header.setAlignment(Qt.AlignCenter)
        main.addWidget(self._mgr_header)
        main.addSpacing(4)

        tabs = QTabWidget()
        ord_tab = QWidget()
        ol = QVBoxLayout(ord_tab)
        ol.setSpacing(8)
        mol = QLabel("All Orders")
        mol.setObjectName("section")
        ol.addWidget(mol)
        mint = QLabel("Select a row to view receipt")
        mint.setObjectName("hint")
        mint.setWordWrap(True)
        ol.addWidget(mint)
        mgr_order_stack = QWidget()
        mgr_order_lay = QVBoxLayout(mgr_order_stack)
        mgr_order_lay.setContentsMargins(0, 0, 0, 0)
        mgr_order_lay.setSpacing(8)
        self._ord_table = QTableWidget(0, 5)
        self._ord_table.setHorizontalHeaderLabels(["Order #", "Customer", "Status", "Total", "Placed"])
        self._apply_header_alignments(
            self._ord_table,
            Qt.AlignLeft,
            Qt.AlignLeft,
            Qt.AlignLeft,
            Qt.AlignRight,
            Qt.AlignLeft,
        )
        _oh = self._ord_table.horizontalHeader()
        _oh.setSectionResizeMode(0, QHeaderView.Fixed)
        _oh.setSectionResizeMode(1, QHeaderView.Stretch)
        _oh.setSectionResizeMode(2, QHeaderView.Fixed)
        _oh.setSectionResizeMode(3, QHeaderView.Fixed)
        _oh.setSectionResizeMode(4, QHeaderView.Fixed)
        self._ord_table.setColumnWidth(0, 88)
        self._ord_table.setColumnWidth(2, 88)
        self._ord_table.setColumnWidth(3, 112)
        self._ord_table.setColumnWidth(4, 160)
        self._lock_table_row_sizes(self._ord_table)
        self._ord_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._ord_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._ord_table.setAlternatingRowColors(True)
        self._ord_table.setShowGrid(False)
        self._apply_table_selection(self._ord_table)
        self._mgr_ord_detail = QTextBrowser()
        self._mgr_ord_detail.setObjectName("orderDetail")
        self._mgr_ord_detail.setMinimumHeight(120)
        self._mgr_ord_detail.setHtml(format_order_html(None))
        mgr_order_lay.addWidget(self._ord_table, 1)
        mgr_order_lay.addWidget(self._mgr_ord_detail, 1)
        ol.addWidget(mgr_order_stack, 1)

        def sync_mgr_detail():
            r = self._ord_table.currentRow()
            if r < 0 or r >= len(self._mgr_orders_cache):
                self._mgr_ord_detail.setHtml(format_order_html(None))
                return
            self._mgr_ord_detail.setHtml(format_order_html(self._mgr_orders_cache[r], True))

        self._ord_table.itemSelectionChanged.connect(sync_mgr_detail)
        orow = QHBoxLayout()
        b_bill_open = QPushButton("Open Bill")
        b_bill_print = QPushButton("Print Bill")
        b_paid = QPushButton("Mark as Paid")
        for _b in (b_bill_open, b_bill_print, b_paid):
            _b.setObjectName("ghost")
        b_mgr_ord_sign = QPushButton("Sign out")
        b_mgr_ord_sign.setObjectName("ghost")
        b_mgr_ord_sign.clicked.connect(self._logout)
        orow.addWidget(b_bill_open)
        orow.addWidget(b_bill_print)
        orow.addWidget(b_paid)
        orow.addStretch()
        orow.addWidget(b_mgr_ord_sign)
        ol.addLayout(orow)

        book_tab = QWidget()
        bl = QVBoxLayout(book_tab)
        self._mgr_table = QTableWidget(0, 6)
        self._mgr_table.setHorizontalHeaderLabels(
            ["ID", "Title", "Author", "Buy", "Rent", "Rent OK"]
        )
        self._apply_header_alignments(
            self._mgr_table,
            Qt.AlignLeft,
            Qt.AlignLeft,
            Qt.AlignLeft,
            Qt.AlignRight,
            Qt.AlignRight,
            Qt.AlignRight,
        )
        _mh = self._mgr_table.horizontalHeader()
        _mh.setSectionResizeMode(0, QHeaderView.Fixed)
        _mh.setSectionResizeMode(1, QHeaderView.Stretch)
        _mh.setSectionResizeMode(2, QHeaderView.Stretch)
        for col in (3, 4, 5):
            _mh.setSectionResizeMode(col, QHeaderView.Fixed)
        self._mgr_table.setColumnWidth(0, 64)
        self._mgr_table.setColumnWidth(3, 96)
        self._mgr_table.setColumnWidth(4, 96)
        self._mgr_table.setColumnWidth(5, 92)
        self._lock_table_row_sizes(self._mgr_table)
        self._mgr_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._mgr_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._mgr_table.setAlternatingRowColors(True)
        self._mgr_table.setShowGrid(False)
        self._apply_table_selection(self._mgr_table)
        bl.addWidget(self._mgr_table, 1)

        self._mt = QLineEdit()
        self._ma = QLineEdit()
        self._mb = QLineEdit()
        self._mr = QLineEdit()
        self._mavail = QCheckBox("Rental available")
        self._mavail.setChecked(True)
        book_grid = QGridLayout()
        book_grid.setHorizontalSpacing(20)
        book_grid.setVerticalSpacing(10)
        book_grid.setColumnStretch(1, 1)
        book_grid.setColumnStretch(3, 1)
        book_grid.addWidget(QLabel("Title"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        book_grid.addWidget(self._mt, 0, 1)
        book_grid.addWidget(QLabel("Buy $"), 0, 2, Qt.AlignRight | Qt.AlignVCenter)
        book_grid.addWidget(self._mb, 0, 3)
        book_grid.addWidget(QLabel("Author"), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        book_grid.addWidget(self._ma, 1, 1)
        book_grid.addWidget(QLabel("Rent $"), 1, 2, Qt.AlignRight | Qt.AlignVCenter)
        book_grid.addWidget(self._mr, 1, 3)
        book_grid.addWidget(self._mavail, 2, 0, 1, 4)
        bl.addLayout(book_grid)
        brow = QHBoxLayout()
        b_ld = QPushButton("Load selected into form")
        b_ld.setObjectName("ghost")
        b_sv = QPushButton("Save")
        b_sv.setObjectName("ghost")
        b_mgr_cat_sign = QPushButton("Sign out")
        b_mgr_cat_sign.setObjectName("ghost")
        b_mgr_cat_sign.clicked.connect(self._logout)
        brow.addWidget(b_ld)
        brow.addWidget(b_sv)
        brow.addStretch()
        brow.addWidget(b_mgr_cat_sign)
        bl.addLayout(brow)

        tabs.addTab(ord_tab, "Review Orders")
        tabs.addTab(book_tab, "Edit Catalog")
        main.addWidget(tabs, 1)

        def load_orders():
            def call():
                r = self.api.manager_orders()
                r.raise_for_status()
                return r.json()

            def on_ok(rows):
                self._mgr_orders_cache = list(rows)
                self._ord_table.setRowCount(0)
                for o in rows:
                    r = self._ord_table.rowCount()
                    self._ord_table.insertRow(r)
                    it0 = QTableWidgetItem(str(o["orderId"]))
                    it0.setData(Qt.UserRole, o["orderId"])
                    it0.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    it0.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self._ord_table.setItem(r, 0, it0)
                    c1 = QTableWidgetItem(o.get("customerUsername") or "")
                    c1.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    c1.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self._ord_table.setItem(r, 1, c1)
                    st = o["paymentStatus"]
                    c2 = QTableWidgetItem(st)
                    c2.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    c2.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    if st == "PAID":
                        c2.setForeground(QBrush(QColor("#1d4ed8")))
                    else:
                        c2.setForeground(QBrush(QColor("#b45309")))
                    self._ord_table.setItem(r, 2, c2)
                    c3 = QTableWidgetItem(_money(o["totalAmount"]))
                    c3.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    c3.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self._ord_table.setItem(r, 3, c3)
                    c4 = QTableWidgetItem((o.get("createdAt") or "")[:19])
                    c4.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    c4.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self._ord_table.setItem(r, 4, c4)
                    self._ord_table.setRowHeight(r, TABLE_ROW_HEIGHT_PX)
                if rows:
                    self._ord_table.selectRow(0)
                else:
                    self._mgr_ord_detail.setHtml(format_order_html(None))

            self._run(call, on_ok)

        def mark_paid():
            r = self._ord_table.currentRow()
            if r < 0:
                return
            it = self._ord_table.item(r, 0)
            oid = int(it.data(Qt.UserRole))

            def on_ok(resp):
                if resp.status_code != 200:
                    QMessageBox.critical(self, "Error", resp.text)
                    return
                load_orders()

            self._run(lambda: self.api.manager_payment(oid, "PAID"), on_ok)

        b_bill_open.clicked.connect(self._mgr_open_bill)
        b_bill_print.clicked.connect(self._mgr_print_bill)
        b_paid.clicked.connect(mark_paid)

        def load_books():
            def call():
                r = self.api.search("")
                r.raise_for_status()
                return r.json()

            def on_ok(rows):
                self._mgr_books.clear()
                self._mgr_table.setRowCount(0)
                for b in rows:
                    iid = str(b["id"])
                    self._mgr_books[iid] = b
                    r = self._mgr_table.rowCount()
                    self._mgr_table.insertRow(r)
                    it0 = QTableWidgetItem(str(b["id"]))
                    it0.setData(Qt.UserRole, b["id"])
                    it0.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    it0.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self._mgr_table.setItem(r, 0, it0)
                    for col, val in enumerate(
                        [
                            b["title"],
                            b["author"],
                            _money(b["priceBuy"]),
                            _money(b["priceRent"]),
                            "Y" if b["rentalAvailable"] else "N",
                        ],
                        start=1,
                    ):
                        it = QTableWidgetItem(val)
                        it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                        if col >= 3:
                            it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        else:
                            it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                        self._mgr_table.setItem(r, col, it)
                    self._mgr_table.setRowHeight(r, TABLE_ROW_HEIGHT_PX)

            self._run(call, on_ok)

        def load_sel():
            r = self._mgr_table.currentRow()
            if r < 0:
                return
            it = self._mgr_table.item(r, 0)
            b = self._mgr_books.get(str(int(it.data(Qt.UserRole))))
            if not b:
                return
            self._mt.setText(b["title"])
            self._ma.setText(b["author"])
            self._mb.setText(_money(b["priceBuy"]))
            self._mr.setText(_money(b["priceRent"]))
            self._mavail.setChecked(bool(b["rentalAvailable"]))

        def save_book():
            try:
                payload = {
                    "title": self._mt.text().strip(),
                    "author": self._ma.text().strip(),
                    "priceBuy": _parse_money_field(self._mb.text()),
                    "priceRent": _parse_money_field(self._mr.text()),
                    "rentalAvailable": self._mavail.isChecked(),
                }
            except ValueError:
                QMessageBox.critical(self, "Invalid", "Prices must be numbers.")
                return

            def on_ok(resp, clear_form=False):
                if resp.status_code != 200:
                    QMessageBox.critical(self, "Error", resp.text)
                    return
                load_books()
                if clear_form:
                    self._mt.clear()
                    self._ma.clear()
                    self._mb.clear()
                    self._mr.clear()

            r = self._mgr_table.currentRow()
            if r >= 0:
                it = self._mgr_table.item(r, 0)
                bid = int(it.data(Qt.UserRole))
                self._run(
                    lambda: self.api.manager_update_book(bid, payload),
                    lambda resp: on_ok(resp, False),
                )
            else:
                self._run(
                    lambda: self.api.manager_create_book(payload),
                    lambda resp: on_ok(resp, True),
                )

        b_ld.clicked.connect(load_sel)
        b_sv.clicked.connect(save_book)
        self._mgr_load_orders = load_orders
        self._mgr_load_books = load_books
        return w


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    app.setFont(QFont(".AppleSystemUIFont", 13))
    win = BookstoreWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
