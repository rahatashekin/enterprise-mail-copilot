"""
Rigorous Multi-Turn Thread Auditor (Live Streaming Version)
Thread ID: 1943f2b241d2da98 (Soft Iron Pressure Seal Rings - 18 Turns)

Audits 4 key pivotal incoming turns from powergen_a facility_a:
  - Turn 01: Initial Request for Price Justification
  - Turn 06: Price Objection / Rejection by Plant
  - Turn 10: Official Negotiation Meeting Call
  - Turn 15: Senior Manager Escalation (Imran Hossain stepping in)

Appends incrementally to data/thread_18_turns_audit.md
"""

import json, sys, time
from pathlib import Path
from google import genai

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
OUT_FILE = DATA_DIR / "thread_18_turns_audit.md"

key = (CONFIG_DIR / "gemini_api_key.txt").read_text(encoding="utf-8").strip()
client = genai.Client(api_key=key)

with open(DATA_DIR / "powerplant_emails.json", 'r', encoding='utf-8') as f:
    emails = json.load(f)

thread_msgs = [e for e in emails if e.get('thread_id') == '1943f2b241d2da98']
thread_msgs.sort(key=lambda x: int(x.get('internal_date', 0)))

pivotal_turns = [
    (0, "Turn 01 (07-Jan-2025): Initial Price Justification Request"),
    (5, "Turn 06 (08-Mar-2025): Price Rejection (Quoted price is higher than Ref PO)"),
    (9, "Turn 10 (07-Apr-2025): Official Negotiation Meeting Call at Site"),
    (14, "Turn 15 (19-Apr-2025): Senior Manager Escalation (Imran Hossain Demands Cost Breakdown)")
]

prompt_template = """
You are an executive procurement copilot for Enterprise Trading Corporation (Procurement Lead / Executive).
This is TURN #{turn_num} of an ongoing 18-turn high-stakes negotiation with powergen_a Power Generation Facility A for:
"PROCUREMENT OF HIGH-PRESSURE VALVES SOFT IRON PRESSURE SEAL RING (Quote: USD 26,928.00)"

Incoming Message Details:
- Date: {date}
- Sender: {sender}
- Subject: {subject}
- Full Email Body:
{body}

Historical Context so far:
- Total turns so far: {turn_num}
- Previous turns summary: {prev_summary}

TASK:
1. WHAT IS THE EXACT SITUATION AT THIS SPECIFIC TURN?
   (e.g., Routine inquiry, Serious price objection/rejection, In-person meeting call, or Senior executive escalation?)

2. GENERATE THE EXACT EXECUTIVE WHATSAPP ALERT FOR Executive:
   Must be in sharp, highly respectful, executive business Bengali.
   Must highlight:
   - বায়ারের বর্তমান অবস্থান ও আসল উদ্দেশ্য (Buyer's exact stance & psychological intent)
   - ব্যবসার ঝুঁকি বা সুযোগ (Commercial Risk or Win Opportunity)
   - মামার তাৎক্ষণিক সুনির্দিষ্ট অ্যাকশন (Single Most Critical Action Item)
   - মিটিং বা সময়সীমা (যদি থাকে)

3. AUDITOR'S CRITIQUE:
   Why will this specific alert save Executive from losing the USD 26,928 deal?
"""

OUT_FILE.write_text("# 18-TURN LONG-THREAD TURN-BY-TURN AUDIT REPORT\n\n", encoding="utf-8")
rolling_context = "Initial tender enquiry issued for Soft Iron Pressure Seal Rings."

for idx, label in pivotal_turns:
    msg = thread_msgs[idx]
    turn_no = idx + 1
    sender = msg.get('headers', {}).get('from', '')
    date = msg.get('headers', {}).get('date', '')
    subj = msg.get('headers', {}).get('subject', '')
    body = msg.get('body', '')

    print(f"--> [Auditing Turn {turn_no:02d}] {label}...", flush=True)

    p = prompt_template.format(
        turn_num=turn_no,
        date=date,
        sender=sender,
        subject=subj,
        body=body[:2000],
        prev_summary=rolling_context
    )

    try:
        res = client.models.generate_content(model="gemini-3.6-flash", contents=p)
        content = res.text.strip()
        section = f"\n{'='*75}\n🎯 {label}\nMessage ID: {msg.get('id')} | Sender: {sender} | Date: {date}\n{'-'*75}\n{content}\n{'='*75}\n"
        with open(OUT_FILE, 'a', encoding='utf-8') as f:
            f.write(section)
        print(f"    ✓ Turn {turn_no:02d} Completed & Saved.", flush=True)
    except Exception as e:
        print(f"    ❌ Turn {turn_no:02d} Error: {e}", flush=True)

    rolling_context += f" | Turn {turn_no} ({date[:11]}): {sender[:20]} wrote: {body[:150]}"
    time.sleep(2)

print("\nAll pivotal turns audited successfully!", flush=True)
