#!/usr/bin/env python3
"""Build Tieout's synthetic demo fixture: a mid-market company's bank statement
vs its general ledger cash account for one period, with realistic, planted
reconciliation breaks and control-risk patterns. Deterministic (no randomness)
so the demo is stable. ALL DATA IS SYNTHETIC."""
import json, os

COMPANY = "Harbor Point Logistics, Inc."
PERIOD = "September 2026"
OPENING = 482150.00

# Each row: id, date (YYYY-MM-DD), amount (negative = cash out), party, memo.
# GL rows may carry preparer/approver for segregation-of-duties checks.
bank, gl = [], []

def pair(d, amt, party, memo, bank_date=None, gl_date=None):
    """A clean matched transaction: appears on both sides."""
    bank.append({"id": f"B{len(bank)+1:03d}", "date": bank_date or d, "amount": amt, "party": party, "memo": memo})
    gl.append({"id": f"G{len(gl)+1:03d}", "date": gl_date or d, "amount": amt, "party": party, "memo": memo})

# --- 22 clean matched transactions (the bulk that should just tie out) ---
pair("2026-09-02",  96500.00, "Acme Freight Co",      "Customer deposit INV-5521")
pair("2026-09-02", -41200.00, "Seaboard Payroll",     "Payroll run 09/01")
pair("2026-09-03", -8800.00,  "Gulf Coast Fuel",      "ACH fuel settlement")
pair("2026-09-04",  52300.00, "Trident Shipping",     "Customer deposit INV-5529")
pair("2026-09-05", -15400.00, "Harborview Realty",    "Warehouse lease 09/2026")
pair("2026-09-08", -2650.00,  "Pinnacle Insurance",   "Cargo policy premium")
pair("2026-09-09",  74800.00, "Lone Star Distributors","Customer deposit INV-5540")
pair("2026-09-10", -3180.00,  "CloudOps Systems",     "SaaS fleet telematics")
pair("2026-09-11", -41200.00, "Seaboard Payroll",     "Payroll run 09/11")
pair("2026-09-12", -6420.00,  "Gulf Coast Fuel",      "ACH fuel settlement")
pair("2026-09-15",  61250.00, "Acme Freight Co",      "Customer deposit INV-5551")
pair("2026-09-16", -9900.00,  "Rapid Parts Supply",   "Fleet maintenance parts")
pair("2026-09-17",  43900.00, "Delmar Logistics",     "Customer deposit INV-5558")
pair("2026-09-18", -2100.00,  "City of Tampa",        "Permit renewal")
pair("2026-09-22", -8800.00,  "Gulf Coast Fuel",      "ACH fuel settlement")
pair("2026-09-23",  88400.00, "Trident Shipping",     "Customer deposit INV-5566")
pair("2026-09-24", -41200.00, "Seaboard Payroll",     "Payroll run 09/23")
pair("2026-09-25", -5600.00,  "Rapid Parts Supply",   "Fleet maintenance parts")
pair("2026-09-26",  57700.00, "Lone Star Distributors","Customer deposit INV-5574")
pair("2026-09-29", -3180.00,  "CloudOps Systems",     "SaaS fleet telematics")
pair("2026-09-29", -1875.00,  "Apex Legal",           "Contract review fees")
pair("2026-09-30",  39600.00, "Delmar Logistics",     "Customer deposit INV-5582")

# --- Planted reconciliation breaks (what the agent must catch) ---
# B1 Deposit in transit: booked 09/30, clears at the bank 10/01 (next period) -> GL only.
gl.append({"id": f"G{len(gl)+1:03d}", "date": "2026-09-30", "amount": 38420.00, "party": "Acme Freight Co", "memo": "Customer deposit INV-5588"})

# B2 Outstanding check: issued/booked 09/27, not yet cleared -> GL only.
gl.append({"id": f"G{len(gl)+1:03d}", "date": "2026-09-27", "amount": -7850.00, "party": "Coastal Repairs LLC", "memo": "Check #1042 dry dock repair"})

# B3 Duplicate payment at the bank: same ACH hits twice; GL booked once.
gl.append({"id": f"G{len(gl)+1:03d}", "date": "2026-09-15", "amount": -12300.00, "party": "Meridian Fuel", "memo": "ACH bulk diesel"})
bank.append({"id": f"B{len(bank)+1:03d}", "date": "2026-09-15", "amount": -12300.00, "party": "Meridian Fuel", "memo": "ACH bulk diesel"})
bank.append({"id": f"B{len(bank)+1:03d}", "date": "2026-09-16", "amount": -12300.00, "party": "Meridian Fuel", "memo": "ACH bulk diesel"})

# B4 Unbooked receipt: wire in at the bank, never booked in the GL.
bank.append({"id": f"B{len(bank)+1:03d}", "date": "2026-09-12", "amount": 54000.00, "party": "Northgate Capital", "memo": "Incoming wire ref NG-7781"})

# B5 Transposition error: GL $4,120.00 vs bank $4,210.00.
gl.append({"id": f"G{len(gl)+1:03d}", "date": "2026-09-09", "amount": -4120.00, "party": "Dunbar Office Supply", "memo": "Office supplies PO-3390"})
bank.append({"id": f"B{len(bank)+1:03d}", "date": "2026-09-09", "amount": -4210.00, "party": "Dunbar Office Supply", "memo": "Office supplies PO-3390"})

# B6 Bank service charge not booked.
bank.append({"id": f"B{len(bank)+1:03d}", "date": "2026-09-30", "amount": -45.00, "party": "First Harbor Bank", "memo": "Monthly service charge"})

# B7 FX rounding on an international payment: GL 12,490.00 vs bank 12,487.33.
gl.append({"id": f"G{len(gl)+1:03d}", "date": "2026-09-22", "amount": -12490.00, "party": "Lyon Logistique SARL", "memo": "Intl freight EUR invoice"})
bank.append({"id": f"B{len(bank)+1:03d}", "date": "2026-09-22", "amount": -12487.33, "party": "Lyon Logistique SARL", "memo": "Intl freight EUR invoice"})

# --- Control-risk patterns (matched on both sides, flagged by the controls pass) ---
# C1 Round-dollar weekend payment to a brand-new vendor.
pair("2026-09-19", -10000.00, "QuickPay LLC", "Consulting services")  # 2026-09-19 is a Saturday
# C2 Structuring: two payments just under a 10k approval threshold, new vendor, same week.
gl.append({"id": f"G{len(gl)+1:03d}", "date": "2026-09-10", "amount": -9800.00, "party": "Volt Contracting", "memo": "Site work phase 1", "preparer": "a.reyes", "approver": "m.okafor"})
bank.append({"id": f"B{len(bank)+1:03d}", "date": "2026-09-10", "amount": -9800.00, "party": "Volt Contracting", "memo": "Site work phase 1"})
gl.append({"id": f"G{len(gl)+1:03d}", "date": "2026-09-11", "amount": -9750.00, "party": "Volt Contracting", "memo": "Site work phase 2", "preparer": "a.reyes", "approver": "m.okafor"})
bank.append({"id": f"B{len(bank)+1:03d}", "date": "2026-09-11", "amount": -9750.00, "party": "Volt Contracting", "memo": "Site work phase 2"})
# C3 Segregation-of-duties break: same user prepared and approved a reversal.
gl.append({"id": f"G{len(gl)+1:03d}", "date": "2026-09-18", "amount": -3200.00, "party": "Delmar Logistics", "memo": "Credit memo reversal CM-204", "preparer": "j.harmon", "approver": "j.harmon"})
bank.append({"id": f"B{len(bank)+1:03d}", "date": "2026-09-18", "amount": -3200.00, "party": "Delmar Logistics", "memo": "Credit memo reversal CM-204"})

data = {
    "company": COMPANY,
    "period": PERIOD,
    "period_end": "2026-09-30",
    "opening_balance": OPENING,
    "synthetic": True,
    "bank": bank,
    "gl": gl,
}
base = os.path.join(os.path.dirname(__file__), "..")
with open(os.path.join(base, "data.json"), "w") as f:
    json.dump(data, f, indent=2)
# Also emit a plain script so the page loads without fetch (works on file:// and deployed).
with open(os.path.join(base, "data.js"), "w") as f:
    f.write("window.TIEOUT_DATA = " + json.dumps(data) + ";\n")
print(f"wrote data.json + data.js: {len(bank)} bank rows, {len(gl)} GL rows")
