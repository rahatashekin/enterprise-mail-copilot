"""
Single-Turn Interactive Lifecycle Tester
Current Target: STAGE 3 (Notification of Award - NOA / Purchase Order)
Message ID: 18c06634177b81e3
Attachment: data/noa_edwards.pdf (Scanned 2-Page Official NOA Letter)
"""

import sys, json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.main_worker import TenderCopilotWorker

DATA_DIR = PROJECT_ROOT / "data"
EMAILS_FILE = DATA_DIR / "powerplant_emails.json"
NOA_PDF = DATA_DIR / "noa_edwards.pdf"

def main():
    target_msg_id = "18c06634177b81e3"
    worker = TenderCopilotWorker()

    # Clear target_msg_id from state so it processes fresh
    if target_msg_id in worker.state_mgr.state.get("processed_messages", {}):
        del worker.state_mgr.state["processed_messages"][target_msg_id]
        worker.state_mgr._save_state()

    with open(EMAILS_FILE, 'r', encoding='utf-8') as f:
        emails = json.load(f)

    email_obj = next(e for e in emails if e.get('id') == target_msg_id)

    # Reconstruct full prior negotiation history leading up to the award
    dialogue_history = [
        {
            "turn": 1,
            "party": "Buyer / Plant (Quazi Noor Uddin)",
            "date": "14.09.2023",
            "snippet": "Issued Tender Document powergen_a/Site C&M/2023-24/32 for Edwards Vacuum pump spares."
        },
        {
            "turn": 2,
            "party": "Buyer / Plant (Quazi Noor Uddin)",
            "date": "04.10.2023",
            "snippet": "Bid price higher than budgetary price. Demanded price justification documents & suitable discounts."
        },
        {
            "turn": 3,
            "party": "Enterprise Solutions (Vendor)",
            "date": "07.10.2023",
            "snippet": "Submitted past POs/documents. Stated dollar crisis & import cost constraints."
        },
        {
            "turn": 4,
            "party": "Enterprise Solutions (Vendor)",
            "date": "10.10.2023",
            "snippet": "Conceded formal 3% (three percent) discount from total quoted price."
        },
        {
            "turn": 5,
            "party": "Buyer / Plant (Quazi Noor Uddin)",
            "date": "15.10.2023",
            "snippet": "Challenged budgetary price. Demanded proper explanation."
        },
        {
            "turn": 6,
            "party": "Enterprise Solutions (Vendor)",
            "date": "16.10.2023",
            "snippet": "Defended 3% discount offer as final and best possible commercial rate."
        }
    ]

    print("=" * 75)
    print("🚀 PROCESSING STAGE 3 OF LIFECYCLE (NOTIFICATION OF AWARD - NOA)")
    print("=" * 75)
    print(f"From:    {email_obj.get('headers',{}).get('from')}")
    print(f"Date:    {email_obj.get('headers',{}).get('date')}")
    print(f"Subject: {email_obj.get('headers',{}).get('subject')}")
    print(f"Doc:     {NOA_PDF.name} ({NOA_PDF.stat().st_size // 1024} KB Scanned PDF)")
    print("-" * 75)

    # Run Worker on NOA with attached PDF and full dialogue history
    res = worker.process_message(
        message_id=target_msg_id,
        email_obj=email_obj,
        attachment_files=[NOA_PDF],
        dialogue_history=dialogue_history
    )

    print("\n[STEP 1: DETECTED LIFECYCLE STAGE]")
    print(f"Stage: {res.get('lifecycle_stage')}")

    print("\n[STEP 2: EXTRACTED DYNAMIC SS2 VARIABLES]")
    for k, v in res.get('extracted_data', {}).items():
        print(f"  • {k:<22} : {v}")

    print("\n" + "=" * 75)
    print("📱 GENERATED CORPORATE EXECUTIVE WHATSAPP ALERT (SS1 FORMAT):")
    print("=" * 75)
    print(res.get('alert_message'))
    print("=" * 75)

if __name__ == "__main__":
    main()
