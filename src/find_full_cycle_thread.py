import json
from pathlib import Path

DATA_DIR = Path(r"C:\Users\Home\Documents\PythonProjects\digital-corporation\data")
with open(DATA_DIR / "powerplant_emails.json", "r", encoding="utf-8") as f:
    emails = json.load(f)

threads = {}
for e in emails:
    tid = e.get("thread_id")
    if tid:
        threads.setdefault(tid, []).append(e)

for tid in threads:
    threads[tid].sort(key=lambda x: int(x.get("internal_date", 0)))

lifecycle_matches = []

for tid, msgs in threads.items():
    all_text = " ".join([
        (m.get("headers", {}).get("subject", "") + " " + m.get("body", "") + " " + " ".join([a.get("filename", "") for a in m.get("attachments", [])]))
        for m in msgs
    ]).lower()

    has_rfq = any(k in all_text for k in ["rfq", "nit", "enquiry", "tender document", "quotation invited", "request for quotation"])
    has_quote = any(k in all_text for k in ["quotation", "quoted price", "our offer", "submitted our offer", "price offer"])
    has_po = any(k in all_text for k in ["purchase order", "po no", "contract agreement", "work order", "notification of award", "noa"])
    has_delivery = any(k in all_text for k in ["delivery", "challan", "dispatch", "goods delivery", "consignment", "material supply"])
    has_payment_pg = any(k in all_text for k in ["bill", "payment", "performance guarantee", "pg release", "security deposit", "retention"])

    score = sum([has_rfq, has_quote, has_po, has_delivery, has_payment_pg])

    if score >= 4:
        d_start = msgs[0].get("headers", {}).get("date", "")[:16]
        d_end = msgs[-1].get("headers", {}).get("date", "")[:16]
        lifecycle_matches.append({
            "thread_id": tid,
            "turns": len(msgs),
            "subject": msgs[0].get("headers", {}).get("subject", ""),
            "score": score,
            "stages": {
                "RFQ": has_rfq,
                "Quote": has_quote,
                "PO": has_po,
                "Delivery": has_delivery,
                "Payment_PG": has_payment_pg
            },
            "dates": f"{d_start} to {d_end}"
        })

lifecycle_matches.sort(key=lambda x: (x["score"], x["turns"]), reverse=True)

print(f"Found {len(lifecycle_matches)} threads with >= 4 completed lifecycle stages:\n")
for i, m in enumerate(lifecycle_matches[:10], 1):
    print(f"{i}. Thread ID: [{m['thread_id']}] | Turns: {m['turns']} | Score: {m['score']}/5 | Dates: {m['dates']}")
    print(f"   Subject: {m['subject'][:80]}")
    print(f"   Stages:  {m['stages']}\n")
