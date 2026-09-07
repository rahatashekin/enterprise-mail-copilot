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

found_single_threads = []

for tid, msgs in threads.items():
    msgs.sort(key=lambda x: int(x.get("internal_date", 0)))

    stages_detected = {
        "1_RFQ": False,
        "2_QUOTE": False,
        "3_NEGOTIATION": False,
        "4_PO_AWARD": False,
        "5_DELIVERY": False,
        "6_PAYMENT_PG": False
    }

    turn_details = []

    for idx, m in enumerate(msgs, 1):
        text = (m.get("headers", {}).get("subject", "") + " " + m.get("body", "") + " " + " ".join([a.get("filename", "") for a in m.get("attachments", [])])).lower()
        sender = m.get("headers", {}).get("from", "").lower()
        is_self = "enterprise.automation@example.com" in sender

        stage_this_turn = []
        if any(k in text for k in ["nit :", "nit:", "rfq", "issuance of tender document", "tender enquiry", "invitation for bid"]):
            stages_detected["1_RFQ"] = True
            stage_this_turn.append("RFQ")
        if is_self and any(k in text for k in ["quoted", "our offer", "quotation", "price offer", "submitted our bid", "bid proposal"]):
            stages_detected["2_QUOTE"] = True
            stage_this_turn.append("QUOTE")
        if any(k in text for k in ["price justification", "price breakup", "discount", "higher than", "clarification"]):
            stages_detected["3_NEGOTIATION"] = True
            stage_this_turn.append("NEGOTIATION")
        if any(k in text for k in ["purchase order", "po no", "placed an order", "contract agreement", "noa", "work order"]):
            stages_detected["4_PO_AWARD"] = True
            stage_this_turn.append("PO")
        if any(k in text for k in ["challan", "dispatch", "goods delivery", "carrier", "lorry", "consignment"]):
            stages_detected["5_DELIVERY"] = True
            stage_this_turn.append("DELIVERY")
        if any(k in text for k in ["bill processing", "bill payment", "performance guarantee", "pg release", "retention money"]):
            stages_detected["6_PAYMENT_PG"] = True
            stage_this_turn.append("PAYMENT/PG")

        turn_details.append((idx, m.get("headers", {}).get("date", "")[:16], "Executive" if is_self else "Plant", stage_this_turn, m.get("body", "").replace("\n", " ")[:60]))

    completed_count = sum(1 for k, v in stages_detected.items() if v)
    if completed_count >= 4:
        found_single_threads.append({
            "thread_id": tid,
            "turns": len(msgs),
            "stages": stages_detected,
            "completed_count": completed_count,
            "subject": msgs[0].get("headers", {}).get("subject", ""),
            "turn_details": turn_details
        })

found_single_threads.sort(key=lambda x: (x["completed_count"], x["turns"]), reverse=True)

print(f"Found {len(found_single_threads)} single threads with >=4 lifecycle stages inside the same thread:\n")
for i, t in enumerate(found_single_threads[:5], 1):
    tid = t["thread_id"]
    turns = t["turns"]
    score = t["completed_count"]
    subj = t["subject"]
    stages = t["stages"]
    print(f"Option {i}: Thread ID [{tid}] | Turns: {turns} | Stages: {score}/6")
    print(f"  Subject: {subj[:75]}")
    print(f"  Stages: {stages}")
    print("  Turn Progression:")
    for turn_no, d, who, st, snip in t["turn_details"][:8]:
        print(f"    Turn {turn_no:02d} ({d}) [{who}]: {st} -> {snip}...")
    print("-" * 75)
