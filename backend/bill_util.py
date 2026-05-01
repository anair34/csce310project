import html
from decimal import Decimal
from pathlib import Path

from .models import OrderLineType


def _bill_money(value) -> str:
    return f"${Decimal(str(value)):.2f}"


def write_order_bill(order, bills_dir):
    Path(bills_dir).mkdir(parents=True, exist_ok=True)
    path = Path(bills_dir) / f"bill-{order.id}.html"
    rows = []
    for line in order.lines:
        lt = "Purchase" if line.line_type == OrderLineType.BUY else "Rental"
        line_total = Decimal(str(line.unit_price)) * line.quantity
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td class=\"num\">{}</td>"
            "<td class=\"num\">{}</td><td class=\"num\">{}</td></tr>".format(
                html.escape(line.book.title),
                html.escape(line.book.author),
                lt,
                line.quantity,
                _bill_money(line.unit_price),
                _bill_money(line_total),
            )
        )
    created = order.created_at.isoformat() if order.created_at else ""
    body = (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\"><title>Bill #{}</title>"
        "<style>body{{font-family:system-ui,-apple-system,sans-serif;max-width:720px;margin:2rem auto;"
        "color:#1a1a2e;}}h1{{font-size:1.25rem;}}table{{width:100%;border-collapse:collapse;margin-top:1rem;}}"
        "th,td{{border:1px solid #ccc;padding:0.5rem 0.75rem;text-align:left;}}"
        "th{{background:#16213e;color:#eee;}}.num{{text-align:right;}}"
        ".total{{font-weight:700;font-size:1.1rem;margin-top:1rem;}}.meta{{color:#444;font-size:0.9rem;}}</style></head><body>"
        "<h1>Order bill</h1><p class=\"meta\">Order ID: <strong>{}</strong><br>Date: {}<br>Payment: {}</p>"
        "<table><thead><tr><th>Title</th><th>Author</th><th>Type</th><th>Qty</th>"
        "<th>Unit price</th><th>Line total</th></tr></thead><tbody>{}</tbody></table>"
        "<p class=\"total\">Total due: {}</p></body></html>"
    ).format(
        order.id,
        order.id,
        created,
        order.payment_status.value,
        "".join(rows),
        _bill_money(order.total_amount),
    )
    path.write_text(body, encoding="utf-8")
    return str(path.resolve())
