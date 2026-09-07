"""
Unit Tests for ProjectGraph Engine
Verifies:
  1. Database initialization and table creation.
  2. Alias extraction from email text and attachments.
  3. Resolution of disjoint threads into a single Project Dossier.
  4. Chronological cross-thread history retrieval.
"""

import sys, os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.project_graph import ProjectGraph

TEST_DB_PATH = PROJECT_ROOT / "data" / "test_project_graph.db"

def test_project_graph():
    if TEST_DB_PATH.exists():
        os.remove(TEST_DB_PATH)

    graph = ProjectGraph(db_path=TEST_DB_PATH)

    # -------------------------------------------------------------
    # Test 1: First Incoming Message (Thread A - RFQ)
    # -------------------------------------------------------------
    email_thread_a = {
        "id": "msg_001_rfq",
        "thread_id": "thread_alpha_rfq",
        "headers": {
            "subject": "Regarding issuance of Tender Document for Edwards Rotary vane vacuum pump (powergen_a /Site C&M/2023-24/32)",
            "from": "Quazi Noor Uddin <noorquazi225@energy-utility.com>",
            "date": "14.09.2023"
        },
        "body": "We hereby issue tender enquiry powergen_a/Site C&M/2023-24/32 for Edwards pump spares.",
        "attachments": [{"filename": "Tender_Document_2023_24_32.pdf"}]
    }

    proj_id, is_new = graph.resolve_or_create_project(email_thread_a)
    assert is_new is True, "First message should create a new project dossier"
    print(f"✅ Test 1 Passed: Created Project [{proj_id}] for Thread A")

    # Record Event for Thread A
    graph.record_event(
        project_id=proj_id,
        thread_id="thread_alpha_rfq",
        message_id="msg_001_rfq",
        timestamp="2023-09-14T10:00:00Z",
        sender="noorquazi225@energy-utility.com",
        is_outgoing=False,
        stage="1_NEW_RFQ",
        summary_text="Tender Document issued for Edwards Pump. Deadline: 25.09.2023.",
        extracted_data={"tender_no": "powergen_a/Site C&M/2023-24/32", "plant_name": "powergen_a facility_a"}
    )

    # -------------------------------------------------------------
    # Test 2: Second Message (Thread B - DISJOINT THREAD for NOA!)
    # Notice: thread_id is completely different ("thread_beta_noa")
    # -------------------------------------------------------------
    email_thread_b = {
        "id": "msg_002_noa",
        "thread_id": "thread_beta_noa",  # << DIFFERENT THREAD!
        "headers": {
            "subject": "Notification of Award (NOA) for Edwards Rotary vane vacuum pump",
            "from": "Mehedi Hasan <mehedi@energy-utility.com>",
            "date": "25.11.2023"
        },
        "body": "Notification of Award (NOA) issued against Ref: powergen_a/Site C&M/2023-24/32.",
        "attachments": [{"filename": "NOA_338.pdf"}]
    }

    resolved_proj_id, is_new_b = graph.resolve_or_create_project(email_thread_b)
    assert is_new_b is False, "Second message in different thread MUST match existing project!"
    assert resolved_proj_id == proj_id, f"Should resolve to [{proj_id}], got [{resolved_proj_id}]"
    print(f"✅ Test 2 Passed: Disjoint Thread B successfully linked to existing Project [{resolved_proj_id}]!")

    # Record Event for Thread B
    graph.record_event(
        project_id=resolved_proj_id,
        thread_id="thread_beta_noa",
        message_id="msg_002_noa",
        timestamp="2023-11-25T12:00:00Z",
        sender="mehedi@energy-utility.com",
        is_outgoing=False,
        stage="3_PO_AWARD",
        summary_text="NOA issued. Value: BDT 8,47,780.00. PO No: 322300161.",
        extracted_data={"tender_no": "powergen_a/Site C&M/2023-24/32", "po_number": "322300161", "total_contract_value": "BDT 8,47,780.00"}
    )

    # -------------------------------------------------------------
    # Test 3: Third Message (Thread C - PO Retention / Payment!)
    # Notice: Only mentions PO 322300161, does NOT mention tender number!
    # -------------------------------------------------------------
    email_thread_c = {
        "id": "msg_003_pg",
        "thread_id": "thread_gamma_bill",  # << 3RD DIFFERENT THREAD!
        "headers": {
            "subject": "Prayer for Release of Retention Money against PO No: 322300161",
            "from": "Procurement Lead <enterprise.automation@example.com>",
            "date": "15.05.2024"
        },
        "body": "We pray for release of 10% retention money against PO: 322300161.",
        "attachments": [{"filename": "Bill_Challan.pdf"}]
    }

    resolved_proj_id_c, is_new_c = graph.resolve_or_create_project(email_thread_c)
    assert is_new_c is False, "Message with PO 322300161 MUST resolve to existing project dossier!"
    assert resolved_proj_id_c == proj_id, f"Should resolve to [{proj_id}], got [{resolved_proj_id_c}]"
    print(f"✅ Test 3 Passed: 3rd Disjoint Thread C matched via PO No [322300161] to Project [{resolved_proj_id_c}]!")

    # -------------------------------------------------------------
    # Test 4: Retrieve Unified Cross-Thread History
    # -------------------------------------------------------------
    timeline = graph.get_cross_thread_history(proj_id)
    assert len(timeline) == 2, f"Should have 2 recorded events, got {len(timeline)}"
    print(f"✅ Test 4 Passed: Retrieved unified timeline across {len(timeline)} disjoint threads:")
    for ev in timeline:
        print(f"   • Turn {ev['turn']} [{ev['date'][:10]}] Thread: {ev['thread_id']} -> {ev['snippet']}")

    summary = graph.get_project_summary(proj_id)
    print(f"\n📊 Project Dossier Summary:")
    print(f"   • Title: {summary['title']}")
    print(f"   • Tender No: {summary['tender_no']}")
    print(f"   • PO No: {summary['po_no']}")
    print(f"   • Value: {summary['contract_value']}")
    print(f"   • Total Linked Threads: {summary['total_linked_threads']}")
    print(f"   • Total Events: {summary['total_events']}")

    # Clean up test DB safely
    try:
        import gc
        gc.collect()
        if TEST_DB_PATH.exists():
            os.remove(TEST_DB_PATH)
    except Exception:
        pass
    print("\n🎉 ALL UNIT TESTS PASSED WITH 100% SUCCESS!")

if __name__ == "__main__":
    test_project_graph()
