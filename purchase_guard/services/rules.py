from decimal import Decimal

def pct_change(current, baseline):
    if baseline in (None, 0):
        return None
    return ((Decimal(str(current)) - Decimal(str(baseline))) / Decimal(str(baseline))) * Decimal("100")

def price_variance_pct(invoice_rate, po_rate):
    return pct_change(invoice_rate, po_rate)

def quantity_variance_pct(invoice_qty, received_qty):
    if received_qty in (None, 0):
        return None
    return abs(pct_change(invoice_qty, received_qty))

def duplicate_key(supplier, bill_no):
    return f"{supplier}::{(bill_no or '').strip().lower()}"

def is_maverick_purchase(has_po):
    return not bool(has_po)

def high_value(amount, threshold):
    return float(amount or 0) >= float(threshold or 0)
