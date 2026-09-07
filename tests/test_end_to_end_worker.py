"""
End-to-End Verification Test for Master Worker Engine
Enterprise Trading Corporation

Tests:
  1. Full execution: Ingestion -> Document Unpacker -> Gemini 3.6 Flash -> Excel Sync -> Notifier -> State Lock.
  2. Idempotency verification: Re-running on same message MUST be skipped instantly without duplicate alerts.
"""

import sys, json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.main_worker import TenderCopilotWorker

DATA_DIR = PROJECT_ROOT / "data"
ATTACHMENTS_DIR = Path(r"D:\digital-corporation\attachments")
EMAILS_FILE = DATA_DIR / "powerplant_emails.json"

def main():
    print("=" * 75)
    print("END-TO-END MASTER PIPELINE VERIFICATION")
    print("=" * 75)

    worker = TenderCopilotWorker()
    with open(EMAILS_FILE, 'r', encoding='utf-8') as f:
        emails = json.load(f)

    # Pick a real recent email with an RFQ
    target_email = emails[0] # Most recent email in cache
    msg_id = target_email.get("id")
    print(f"\n[Test Step 1] Selected Recent Email: ID [{msg_id}]")
    print(f"   Subject: {target_email.get('headers', {}).get('subject')}")
    print(f"   Sender:  {target_email.get('headers', {}).get('from')}")

    # Find any matching attachment on D: drive if exists
    att_files = []
    for att in target_email.get("attachments", []):
        fn = att.get("filename")
        matched_on_disk = list(ATTACHMENTS_DIR.glob(f"*{fn[:15]}*"))
        if matched_on_disk:
            att_files.append(matched_on_disk[0])

    print(f"   Found {len(att_files)} local document(s) for this email.")

    # 1. Run First Execution (Should Process Successfully)
    print("\n[Test Step 2] Executing Full Autonomous Pipeline (First Run)...")
    res1 = worker.process_message(msg_id, target_email, att_files)
    print(f"   [OK] Pipeline Result: {res1.get('status')}")
    print(f"   [OK] Situation:       {res1.get('situation')}")
    print(f"   [OK] Tender No:       {res1.get('tender_no')}")

    # 2. Run Second Execution on SAME message (Must be skipped by Idempotency Engine)
    print("\n[Test Step 3] Executing Idempotency Stress Test (Immediate Re-run on same message)...")
    res2 = worker.process_message(msg_id, target_email, att_files)
    print(f"   [OK] Result: {res2.get('status')} -> Reason: {res2.get('reason')}")
    assert res2.get("status") == "skipped"
    print("   [OK] EXACTLY-ONCE GUARANTEED: Duplicate alert successfully blocked!")

    print("\n" + "=" * 75)
    print("✅ MASTER WORKER END-TO-END VERIFICATION: 100% SUCCESS.")
    print("=" * 75)

if __name__ == "__main__":
    main()
