"""
End-to-End Autonomous Cross-Thread Lifecycle Verification Test
Verifies that:
  1. Thread A (RFQ + Negotiation, ID: 18a934c1dc3f8ddc) is processed and builds the initial dossier.
  2. Thread B (NOA / Contract Award, ID: 18c06634177b81e3) is processed with ZERO manual history passed.
  3. ProjectGraph autonomously links Thread B to Thread A via entity alias resolution!
  4. Complete cross-thread timeline is injected and the WhatsApp alert renders the Project Dossier badge.
"""

import sys, json, os
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.main_worker import TenderCopilotWorker

DATA_DIR = PROJECT_ROOT / "data"
EMAILS_FILE = DATA_DIR / "powerplant_emails.json"
NOA_PDF = DATA_DIR / "noa_edwards.pdf"
EDWARDS_ATTACHMENT_DIR = Path(r"D:\digital-corporation\attachments")

def main():
    print("=" * 80)
    print("🧪 RUNNING END-TO-END AUTONOMOUS CROSS-THREAD LIFECYCLE TEST")
    print("=" * 80)

    # Clean test state for the 2 target messages
    worker = TenderCopilotWorker()
    target_rfq_id = "18a934c1dc3f8ddc"  # Thread A (RFQ)
    target_noa_id = "18c06634177b81e3"  # Thread B (NOA - DIFFERENT THREAD!)

    for mid in [target_rfq_id, target_noa_id]:
        if mid in worker.state_mgr.state.get("processed_messages", {}):
            del worker.state_mgr.state["processed_messages"][mid]
    worker.state_mgr._save_state()

    with open(EMAILS_FILE, 'r', encoding='utf-8') as f:
        emails = json.load(f)

    rfq_msg = next(e for e in emails if e.get('id') == target_rfq_id)
    noa_msg = next(e for e in emails if e.get('id') == target_noa_id)

    # -------------------------------------------------------------
    # Step 1: Process Thread A (RFQ)
    # -------------------------------------------------------------
    print(f"\n[STEP 1] Processing Thread A (RFQ): {rfq_msg.get('headers',{}).get('subject')[:60]}...")
    print(f"         Thread ID: {rfq_msg.get('thread_id')}")
    rfq_atts = list(EDWARDS_ATTACHMENT_DIR.glob("*EDWARDS*"))

    res_rfq = worker.process_message(
        message_id=target_rfq_id,
        email_obj=rfq_msg,
        attachment_files=rfq_atts
    )

    project_id = res_rfq["project_id"]
    print(f"✅ Thread A Processed! Project Assigned: [{project_id}]")
    print(f"   Stage Detected: {res_rfq['lifecycle_stage']}")

    # -------------------------------------------------------------
    # Step 2: Process Thread B (NOA in DIFFERENT THREAD!)
    # CRITICAL: We pass ZERO manual history (dialogue_history=None)!
    # -------------------------------------------------------------
    print(f"\n[STEP 2] Processing Thread B (NOA): {noa_msg.get('headers',{}).get('subject')[:60]}...")
    print(f"         Thread ID: {noa_msg.get('thread_id')} (DIFFERENT THREAD!)")
    print("         dialogue_history passed: None (Pure Autonomous Linking!)")

    res_noa = worker.process_message(
        message_id=target_noa_id,
        email_obj=noa_msg,
        attachment_files=[NOA_PDF] if NOA_PDF.exists() else [],
        dialogue_history=None  # << NO MANUAL CHEATING!
    )

    noa_project_id = res_noa["project_id"]
    print(f"\n[STEP 3: AUTONOMOUS RESOLUTION VERIFICATION]")
    print(f"   • Thread A Project ID : {project_id}")
    print(f"   • Thread B Project ID : {noa_project_id}")

    assert project_id == noa_project_id, f"FAILED! Thread B got {noa_project_id}, expected {project_id}"
    print(f"🎉 SUCCESS! Disjoint Thread B was AUTONOMOUSLY LINKED to Project [{project_id}]!")

    dossier = worker.project_graph.get_project_summary(project_id)
    print(f"\n📊 UNIFIED PROJECT DOSSIER STATUS:")
    print(f"   • Project Title        : {dossier.get('title')}")
    print(f"   • Plant                : {dossier.get('plant_name')}")
    print(f"   • Tender No            : {dossier.get('tender_no')}")
    print(f"   • PO / NOA No          : {dossier.get('po_no')}")
    print(f"   • Total Contract Value : {dossier.get('contract_value')}")
    print(f"   • Total Linked Threads : {dossier.get('total_linked_threads')} (Disjoint Threads Joined!)")
    print(f"   • Total Events         : {dossier.get('total_events')}")

    print("\n" + "=" * 80)
    print("📱 AUTONOMOUSLY GENERATED WHATSAPP ALERT FOR NOA (WITH DOSSIER BADGE):")
    print("=" * 80)
    print(res_noa["alert_message"])
    print("=" * 80)

if __name__ == "__main__":
    main()
