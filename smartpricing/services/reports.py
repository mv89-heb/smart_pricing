from sqlalchemy import func, select
from ..extensions import db
from ..models import DailyEntry, Product, User


def period_report(tenant_id, start_date, end_date, product_id=None, category=None, entry_type=None):
    q = select(DailyEntry, Product, User).join(Product, DailyEntry.product_id == Product.id).outerjoin(User, DailyEntry.recorded_by == User.id).where(DailyEntry.tenant_id == tenant_id, DailyEntry.date >= start_date, DailyEntry.date <= end_date)
    if product_id:
        q = q.where(DailyEntry.product_id == product_id)
    if category:
        q = q.where(Product.category == category)
    if entry_type:
        q = q.where(DailyEntry.entry_type == entry_type)
    rows = db.session.execute(q.order_by(DailyEntry.date.desc(), DailyEntry.id.desc())).all()

    grand = regular = extra = special = 0.0
    qty = 0.0
    days = set()
    products = {}
    categories = {}
    trend = {}
    entries = []
    for entry, product, user in rows:
        total = float(entry.quantity) * float(entry.price_at_time)
        grand += total
        qty += float(entry.quantity)
        days.add(entry.date)
        bucket = entry.entry_type
        if bucket == "regular": regular += total
        elif bucket == "extra": extra += total
        else: special += total
        products.setdefault(product.name, {"qty": 0, "sum": 0.0})
        products[product.name]["qty"] += float(entry.quantity)
        products[product.name]["sum"] += total
        categories[product.category] = categories.get(product.category, 0.0) + total
        key = entry.date.isoformat()
        trend[key] = trend.get(key, 0.0) + total
        entries.append({"id": entry.id, "date": key, "product_name": product.name, "sku": product.sku or "", "category": product.category, "quantity": float(entry.quantity), "unit": product.unit, "price_at_time": float(entry.price_at_time), "total": total, "entry_type": entry.entry_type, "recorded_by": user.name if user else "מערכת", "notes": entry.notes or ""})

    return {"totals": {"grand": grand, "regular": regular, "extra": extra, "special": special, "average": grand / len(entries) if entries else 0.0, "items_sold": qty, "days": len(days)}, "products": [{"name": k, **v} for k, v in sorted(products.items(), key=lambda x: x[1]["sum"], reverse=True)], "categories": [{"category": k, "sum": v} for k, v in categories.items()], "trend": [{"date": k, "sum": v} for k, v in sorted(trend.items())], "entries": entries}
