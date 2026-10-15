import json

SCHEMA = """{
"provider": "KE | LESCO | IESCO",
"tariff": "string",
"sanctioned_load_kw": number,
"bill_month": "YYYY-MM",
"reading_date": "YYYY-MM-DD",
"issue_date": "YYYY-MM-DD",
"due_date": "YYYY-MM-DD",
"previous_reading": number,
"current_reading": number,
"units_consumed": number,
"charges": [{"type": "energy | fixed | fpa | quarterly_adjustment | surcharge | meter_rent | subsidy | other", "amount": number}],
"total_charges": number,
"taxes": [{"type": "gst | electricity_duty | income_tax | municipal_tax | other_tax", "amount": number}],
"total_taxes": number,
"current_bill": number,
"arrears": number,
"payable_within_due_date": number,
"payable_after_due_date": number
}"""

EXAMPLE = {
    "provider": "KE", "tariff": "A1-R", "sanctioned_load_kw": 3, "bill_month": "2026-04",
    "reading_date": "2026-04-03", "issue_date": "2026-04-07", "due_date": "2026-04-21",
    "previous_reading": 8819, "current_reading": 8970, "units_consumed": 151,
    "charges": [{"type": "fixed", "amount": 900}, {"type": "energy", "amount": 1054},
                {"type": "energy", "amount": 663.51}, {"type": "quarterly_adjustment", "amount": 52.91},
                {"type": "fpa", "amount": 125.27}, {"type": "surcharge", "amount": 64.93}],
    "total_charges": 2860.62,
    "taxes": [{"type": "electricity_duty", "amount": 29.41}, {"type": "gst", "amount": 520.21},
              {"type": "municipal_tax", "amount": 20}],
    "total_taxes": 569.62, "current_bill": 3430.24, "arrears": -0.53,
    "payable_within_due_date": 3430, "payable_after_due_date": 3716,
}

RULES = """You are reading an electricity bill image from Pakistan (K-Electric = provider "KE", LESCO, or IESCO).
Bills may be tilted or partly in Urdu, and personal details are covered by grey boxes.
Return ONLY one JSON object with exactly the keys in the schema. Include every key. Use null when a value is not printed, blank, covered by a grey box, or unreadable. Never guess.
Rules:
- Copy values as printed. Do not recalculate, round or correct anything.
- Amounts are numbers in PKR with no currency labels or commas (Rs. 19,964 -> 19964). Credits and subsidies are negative (38209CR -> -38209).
- Dates are YYYY-MM-DD. bill_month is YYYY-MM (MAR 2026 -> 2026-03).
- tariff: exactly as printed. sanctioned_load_kw: from Sanc Load / S.Load / San Load.
- due_date: the last date to pay without a late payment surcharge.
- units_consumed: units billed for the current month, as printed.
- charges: one entry per line in the charges section; skip blank lines and lines printed as 0; keep separate entries when the same type appears more than once.
  Types: energy (cost of units, Variable Upto ... Units, Cost of Electricity, Energy Charges), fixed, fpa (both FPA and FCA), quarterly_adjustment (QTA, Uniform Quarterly Adjustment), surcharge (Additional Surcharge PHL, F.C Surcharge), meter_rent (meter or service rent), subsidy (government subsidy or relief, as a NEGATIVE amount), other.
- total_charges: the printed charges subtotal, or null if none is printed.
- taxes: one entry per line in the tax or government section. Classify by SECTION, not by name.
  Types: gst (sales tax, GST, GST on FPA), electricity_duty (ED), income_tax, municipal_tax (e.g. KE MUCT KMC), other_tax (extra tax, further tax, TV fee).
  If only a combined tax amount is printed, return [] and put that amount in total_taxes.
- total_taxes: the printed tax subtotal, or null.
- current_bill: the printed amount for this month's bill.
- arrears: previous dues carried forward, keep the printed sign; null if blank.
- payable_within_due_date: amount payable by the due date.
- payable_after_due_date: amount payable after the due date; if several late amounts are shown, use the highest.
- Never include names, addresses, CNIC, account, reference, consumer or meter numbers."""


def level1_prompt():
    return (RULES + "\n\nSchema:\n" + SCHEMA +
            "\n\nExample of the output format, taken from training bill KESC_0008 "
            "(never copy its values into another bill):\n" + json.dumps(EXAMPLE))


FACTS_PROMPT = """From this electricity bill image, extract extra details as ONE JSON object with these keys.
Use null or [] when something is not printed or unreadable. Never guess. Numbers are plain numbers in PKR or units.
{
"usage_history": [{"month": "YYYY-MM", "units": number}],
"billing_history": [{"month": "YYYY-MM", "billed_amount": number, "pay_date": "YYYY-MM-DD", "paid_amount": number}],
"charge_lines": [{"label": "as printed", "units": number, "rate": number, "amount": number}],
"energy_share_percent": number,
"tax_share_percent": number,
"late_payment_lines": [{"label": "as printed", "amount": number}],
"message_board": "text in English (translate any Urdu), or null",
"notes": "anything else a customer might ask about (peak/off-peak units, MDI, payments, due dates)"
}
usage_history is the monthly usage chart or table, oldest first, including the current month if shown.
billing_history is the billing and payment history table, oldest first.
charge_lines is every line of the bill calculation table, in order.
Never include names, addresses, CNIC, account, reference, consumer or meter numbers."""


def qa_prompt(bill, facts, derived, questions):
    return f"""You answer a customer's questions about ONE electricity bill. Use ONLY the bill image and the data below. Do not use outside tariff or rate information.
Rules:
- Get the numbers right. Use the PRE-COMPUTED numbers when they apply. Otherwise calculate step by step and double-check against the bill image.
- If the bill does not show something needed, say so plainly instead of guessing.
- Label any estimate as an estimate and explain how you calculated it.
- If a question has more than one reasonable meaning, state the meaning you used or answer both.
- Never include names, addresses, CNIC, account, reference, consumer or meter numbers.
- Write plain English in 1 to 4 sentences, with specific numbers and PKR amounts, even if the bill is in Urdu.

Extracted bill data: {json.dumps(bill, ensure_ascii=False)}
Extra details: {json.dumps(facts, ensure_ascii=False)}
Pre-computed numbers: {json.dumps(derived, ensure_ascii=False)}
Questions: {json.dumps(questions, ensure_ascii=False)}

Return ONLY a JSON object that maps each question id to its answer text, for example {{"Q1": "answer", "Q2": "answer"}}, using exactly the ids given."""