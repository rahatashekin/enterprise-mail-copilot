"""
Test AI-First Master Pipeline on 3 Critical Edge Cases
Enterprise Trading Corporation

Tests:
  - Case 1: Corrigendum-1 (Expected Archetype: TENDER_CORRIGENDUM_AMENDMENT)
  - Case 2: Goods Delivery & Challan (Expected Archetype: GOODS_DELIVERY_CHALLAN)
  - Case 3: Performance Guarantee Release (Expected Archetype: PG_RELEASE_PAYMENT_TRACKING)

Prints generated WhatsApp alerts to verify executive quality.
"""

import sys, json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.main_worker import TenderCopilotWorker

DATA_DIR = PROJECT_ROOT / "data"
EMAILS_FILE = DATA_DIR / "powerplant_emails.json"
STATE_FILE = DATA_DIR / "system_state.json"

def main():
    print("=" * 75)
    print("TESTING AI-FIRST INTELLIGENT CLASSIFICATION & ALERTS")
    print("=" * 75)

    worker = TenderCopilotWorker()
    with open(EMAILS_FILE, 'r', encoding='utf-8') as f:
        emails = json.load(f)

    test_cases = [
        ('19fc1ef616129d23', 'TEST 1: TENDER CORRIGENDUM (AMENDMENT)'),
        ('1a06156108f2246d', 'TEST 2: GOODS DELIVERY & CHALLAN'),
        ('1a0573b1796d22c9', 'TEST 3: PERFORMANCE GUARANTEE RELEASE')
    ]

    # Temporarily remove test IDs from state to allow re-processing
    for mid, _ in test_cases:
        if mid in worker.state_mgr.state.get("processed_messages", {}):
            del worker.state_mgr.state["processed_messages"][mid]
    worker.state_mgr._save_state()

    for mid, title in test_cases:
        print("\n" + "=" * 75)
        print(f"🎯 {title}")
        print("=" * 75)
        email_obj = next((x for x in emails if x['id'] == mid), None)
        if not email_obj:
            print(f"Message ID {mid} not found.")
            continue

        print(f"Subject: {email_obj.get('headers',{}).get('subject')[:70]}...")
        print(f"Sender:  {email_obj.get('headers',{}).get('from')}")

        res = worker.process_message(mid, email_obj, attachment_files=[])
        print(f"\n[Result] Detected Archetype: [{res.get('archetype')}]")
        print(f"[Result] Tender / PO No:    [{res.get('tender_no')}]")

        # Load the formatted message from WhatsAppFormatter to display
        # We can re-format to print the full message
        from src.tender_parser import WhatsAppFormatter
        # The worker saved it to state
        rec = worker.state_mgr.state["processed_messages"].get(mid, {})
        print("\n" + "-" * 60)
        print("📱 FORMATTED WHATSAPP ALERT FOR Executive:")
        print("-" * 60)
        # Fetch the exact extracted data from state or re-display
        # To display full text cleanly:
        ctx = {"current_message_id": mid}
        # Re-extract or print
        print(WhatsAppFormatter.format_alert(res.get('archetype'), worker.state_mgr.state["processed_messages"][mid], ctx))
        print("-" * 60)

    print("\n" + "=" * 75)
    print("✅ AI-FIRST EVALUATION COMPLETE.")
    print("=" * 75)

if __name__ == "__main__":
    main()
