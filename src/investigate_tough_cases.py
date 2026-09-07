"""
Ruthless Investigator Script: Auditing Edge Cases & Classifier Quality
Enterprise Trading Corporation
"""

import json
from pathlib import Path
from google import genai

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"

key = (CONFIG_DIR / "gemini_api_key.txt").read_text(encoding="utf-8").strip()
client = genai.Client(api_key=key)

with open(DATA_DIR / "powerplant_emails.json", 'r', encoding='utf-8') as f:
    emails = json.load(f)

test_ids = [
    '19fc1ef616129d23', # Case 1: Corrigendum-1 with 2 PDFs
    '1a06156108f2246d', # Case 2: Goods Delivery & Challan
    '1a0573b1796d22c9'  # Case 3: Performance Guarantee (PG) Release
]

prompt_template = """
You are a ruthless procurement auditor for Enterprise Trading Corporation.
Examine this email carefully.
Subject: {subject}
Sender: {sender}
Body Snippet: {body}
Attachments: {attachments}

Evaluate:
1. EXACT Procurement Archetype:
   - NEW_TENDER_RFQ (Only if buyer is issuing a fresh tender enquiry)
   - TENDER_CORRIGENDUM_AMENDMENT (If an existing tender's deadline or spec is amended)
   - GOODS_DELIVERY_CHALLAN (If vendor/Executive is notifying delivery of goods against a PO)
   - PG_RELEASE_PAYMENT_TRACKING (If application for release of Bank Guarantee / Security / Bill)
   - ONGOING_PRICE_NEGOTIATION (If price justification / counter-offer)

2. Why this archetype and NOT others?
3. What is the single most critical business action required for Executive?
4. Would Executive be impressed, or annoyed/confused if the system treated this as a 'New Tender Alert'?

Respond in sharp, honest, professional Bangla with clear markdown.
"""

output_lines = []

for mid in test_ids:
    e = next(x for x in emails if x['id'] == mid)
    p = prompt_template.format(
        subject=e['headers'].get('subject'),
        sender=e['headers'].get('from'),
        body=e.get('body', '')[:800],
        attachments=[a['filename'] for a in e.get('attachments', [])]
    )
    res = client.models.generate_content(model='gemini-3.6-flash', contents=p)
    output_lines.append("=" * 75)
    output_lines.append(f"TARGET: {e['headers'].get('subject')}")
    output_lines.append(f"SENDER: {e['headers'].get('from')}")
    output_lines.append("-" * 75)
    output_lines.append(res.text)
    output_lines.append("=" * 75 + "\n")

out_file = DATA_DIR / "tough_cases_investigation.md"
out_file.write_text("\n".join(output_lines), encoding="utf-8")
print(f"Audit completed and written to {out_file}")
