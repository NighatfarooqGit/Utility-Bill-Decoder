import re
from datetime import date

KEYS = ["provider", "tariff", "sanctioned_load_kw", "bill_month", "reading_date", "issue_date",
        "due_date", "previous_reading", "current_reading", "units_consumed", "charges",
        "total_charges", "taxes", "total_taxes", "current_bill", "arrears",
        "payable_within_due_date", "payable_after_due_date"]
CHARGE_TYPES = {"energy", "fixed", "fpa", "quarterly_adjustment", "surcharge",
                "meter_rent", "subsidy", "other"}
TAX_TYPES = {"gst", "electricity_duty", "income_tax", "municipal_tax", "other_tax"}
NUM_FIELDS = ["sanctioned_load_kw", "previous_reading", "current_reading", "units_consumed",
              "total_charges", "total_taxes", "current_bill", "arrears",
              "payable_within_due_date", "payable_after_due_date"]


def to_number(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    neg = s.upper().endswith("CR")
    if neg:
        s = s[:-2]
    s = re.sub(r"[^\d.\-]", "", s)
    if s in ("", "-", ".", "-."):
        return None
    try:
        n = float(s)
    except ValueError:
        return None
    if neg:
        n = -abs(n)
    return int(n) if n == int(n) else n


def to_date(v):
    if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()):
        return v.strip()
    return None


def to_month(v):
    if isinstance(v, str):
        m = re.match(r"^(\d{4}-\d{2})(-\d{2})?$", v.strip())
        if m:
            return m.group(1)
    return None


def to_provider(v):
    s = str(v or "").upper().replace("-", "").replace(" ", "")
    if s in ("KE", "KESC", "KELECTRIC"):
        return "KE"
    if "LESCO" in s:
        return "LESCO"
    if "IESCO" in s:
        return "IESCO"
    return None


def clean_lines(items, allowed, default):
    out = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        amount = to_number(it.get("amount"))
        if amount is None or amount == 0:
            continue
        t = it.get("type") if it.get("type") in allowed else default
        if t == "subsidy" and amount > 0:
            amount = -amount
        out.append({"type": t, "amount": amount})
    return out


def level1(raw):
    raw = raw if isinstance(raw, dict) else {}
    out = {k: None for k in KEYS}
    out["provider"] = to_provider(raw.get("provider"))
    tariff = raw.get("tariff")
    out["tariff"] = str(tariff).strip() if tariff not in (None, "") else None
    out["bill_month"] = to_month(raw.get("bill_month"))
    for k in ("reading_date", "issue_date", "due_date"):
        out[k] = to_date(raw.get(k))
    for k in NUM_FIELDS:
        out[k] = to_number(raw.get(k))
    out["charges"] = clean_lines(raw.get("charges"), CHARGE_TYPES, "other")
    out["taxes"] = clean_lines(raw.get("taxes"), TAX_TYPES, "other_tax")
    return out


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _d(s):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def sanity(b):
    """Return warnings for a human to check without changing extracted data."""
    w = []
    tot = lambda items: sum(i["amount"] for i in items)
    tc, tt, cb = _num(b["total_charges"]), _num(b["total_taxes"]), _num(b["current_bill"])
    if b["charges"] and tc is not None and abs(tot(b["charges"]) - tc) > 1:
        w.append(f"charge lines add up to {tot(b['charges']):.2f} but total_charges is {tc}")
    if b["taxes"] and tt is not None and abs(tot(b["taxes"]) - tt) > 1:
        w.append(f"tax lines add up to {tot(b['taxes']):.2f} but total_taxes is {tt}")
    if not b["taxes"] and tt:
        w.append(f"taxes list is empty but total_taxes is {tt} (fine only if the bill prints one combined tax amount)")
    if None not in (tc, tt, cb) and abs(tc + tt - cb) > 1:
        w.append(f"total_charges + total_taxes = {tc + tt:.2f} but current_bill is {cb}")
    pr, cr, u = _num(b["previous_reading"]), _num(b["current_reading"]), _num(b["units_consumed"])
    if None not in (pr, cr, u) and abs((cr - pr) - u) > 1:
        w.append(f"readings differ by {cr - pr:.2f} but units_consumed is {u}")
    ar, pw = _num(b["arrears"]), _num(b["payable_within_due_date"])
    if None not in (cb, ar, pw) and abs(cb + ar - pw) > 1:
        w.append(f"current_bill + arrears = {cb + ar:.2f} but payable_within_due_date is {pw}")
    rd, iss = _d(b["reading_date"]), _d(b["issue_date"])
    if rd and iss and abs((iss - rd).days) > 45:
        w.append("reading_date and issue_date are far apart: check the year")
    for k in ("previous_reading", "current_reading", "payable_after_due_date"):
        if b[k] is None:
            w.append(f"{k} is null: confirm it is really not printed")
    return w


def derive(bill, facts):
    """Numbers computed in code so the model does not do arithmetic."""
    facts = facts if isinstance(facts, dict) else {}
    d = {}
    cb, tt, tc = _num(bill.get("current_bill")), _num(bill.get("total_taxes")), _num(bill.get("total_charges"))
    units = _num(bill.get("units_consumed"))
    if cb and tt is not None:
        d["taxes_percent_of_current_bill"] = round(tt / cb * 100, 2)
    if cb and tc is not None:
        d["charges_percent_of_current_bill"] = round(tc / cb * 100, 2)
    if cb and units:
        d["average_cost_per_unit_pkr"] = round(cb / units, 2)
    a, w = _num(bill.get("payable_after_due_date")), _num(bill.get("payable_within_due_date"))
    if a is not None and w is not None:
        d["late_payment_extra_pkr"] = round(a - w, 2)
    pr, cr = _num(bill.get("previous_reading")), _num(bill.get("current_reading"))
    if pr is not None and cr is not None:
        d["reading_difference"] = round(cr - pr, 2)

    hist = [h for h in (facts.get("usage_history") or [])
            if isinstance(h, dict) and _num(h.get("units")) is not None]
    if hist:
        last = hist[-1]
        includes_current = (last.get("month") == bill.get("bill_month")
                            or (units is not None and last["units"] == units))
        prev = hist[:-1] if includes_current else hist
        if prev:
            vals = [h["units"] for h in prev]
            avg = sum(vals) / len(vals)
            d["previous_months_count"] = len(prev)
            d["previous_months_average_units"] = round(avg, 1)
            d["highest_previous_month"] = max(prev, key=lambda h: h["units"])
            d["lowest_previous_month"] = min(prev, key=lambda h: h["units"])
            d["most_recent_previous_month"] = prev[-1]
            d["previous_months_above_their_average"] = sum(v > avg for v in vals)
            if units is not None:
                d["current_minus_average_units"] = round(units - avg, 1)
                if avg:
                    d["current_vs_average_percent"] = round((units - avg) / avg * 100, 1)
    bh = [h for h in (facts.get("billing_history") or [])
          if isinstance(h, dict) and _num(h.get("billed_amount")) is not None]
    if bh:
        d["billing_history_average_billed_pkr"] = round(
            sum(h["billed_amount"] for h in bh) / len(bh), 2)
    return d
