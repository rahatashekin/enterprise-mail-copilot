import json, re
from pathlib import Path

DATA_DIR = Path(r"C:\Users\Home\Documents\PythonProjects\digital-corporation\data")
with open(DATA_DIR / "powerplant_emails.json", "r", encoding="utf-8") as f:
    emails = json.load(f)

pos_found = {}
for e in emails:
    text = (e.get("headers", {}).get("subject", "") + " " + e.get("body", "") + " " + " ".join([a.get("filename", "") for a in e.get("attachments", [])]))
    matches = re.findall(r'322\d{6}', text)
    for po in set(matches):
        pos_found.setdefault(po, []).append(e)

print(f"Total distinct 322xxxxxx PO numbers found: {len(pos_found)}")

complete_pos = []
for po, elist in pos_found.items():
    all_text = " ".join([
        (m.get("headers", {}).get("subject", "") + " " + m.get("body", "") + " " + " ".join([a.get("filename", "") for a in m.get("attachments", [])]))
        for m in elist
    ]).lower()

    has_rfq_quote = any(k in all_text for k in ["rfq", "nit", "quotation", "quoted", "bid proposal", "offer"])
    has_po = any(k in all_text for k in ["purchase order", "po no", "placed an order", "signed po"])
    has_delivery = any(k in all_text for k in ["challan", "delivery", "dispatch", "goods delivery", "carrier", "truck"])
    has_pg_payment = any(k in all_text for k in ["performance guarantee", "pg", "retention", "invoice", "bill", "cheque", "payment", "release"])

    distinct_threads = set(m.get("thread_id") for m in elist)
    score = sum([has_rfq_quote, has_po, has_delivery, has_pg_payment])
    if score >= 3:
        complete_pos.append({
            "po": po,
            "emails_count": len(elist),
            "distinct_threads": len(distinct_threads),
            "score": score,
            "has_rfq_quote": has_rfq_quote,
            "has_po": has_po,
            "has_delivery": has_delivery,
            "has_pg_payment": has_pg_payment,
            "sample_subj": elist[0].get("headers", {}).get("subject", "")[:70],
            "first_date": elist[0].get("headers", {}).get("date", "")[:16],
            "last_date": elist[-1].get("headers", {}).get("date", "")[:16]
        })

complete_pos.sort(key=lambda x: (x["score"], x["emails_count"]), reverse=True)
print(f"Found {len(complete_pos)} PO packages with full lifecycle data:\n")
for idx, p in enumerate(complete_pos[:10], 1):
    print(f"{idx}. PO: [{p['po']}] | Score: {p['score']}/4 | Total Mails: {p['emails_count']} across {p['distinct_threads']} thread(s)")
    print(f"   Date Span: {p['first_date']} to {p['last_date']}")
    print(f"   Stages: RFQ/Quote={p['has_rfq_quote']}, PO={p['has_po']}, Delivery={p['has_delivery']}, Payment/PG={p['has_pg_payment']}")
    print(f"   Subject: {p['sample_subj']}\n")
