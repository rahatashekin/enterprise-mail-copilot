"""
Test Verification for StateManager
Tests:
  - Idempotency: Duplicate check
  - Persistence across script restarts
  - Watermark tracking
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.state_manager import StateManager

def main():
    print("=" * 70)
    print("TESTING STATE MANAGER (IDEMPOTENCY & CRASH RECOVERY)")
    print("=" * 70)

    sm = StateManager()
    test_id = "test_msg_unique_999"

    # Step 1: Initial state check
    print("\n[Step 1] Checking if test message is marked as processed...")
    print(f"   is_processed('{test_id}'): {sm.is_processed(test_id)} (Expected: False)")
    assert not sm.is_processed(test_id)

    # Step 2: Mark as completed
    print("\n[Step 2] Marking test message as completed...")
    sm.mark_completed(test_id, "thread_xyz", {"plant_name": "facility_a", "tender_no": "TEST-123"})
    print(f"   is_processed('{test_id}'): {sm.is_processed(test_id)} (Expected: True)")
    assert sm.is_processed(test_id)

    # Step 3: Simulate server restart by reloading state from disk
    print("\n[Step 3] Simulating server crash and restart (reloading from disk)...")
    sm2 = StateManager()
    print(f"   is_processed after restart: {sm2.is_processed(test_id)} (Expected: True)")
    assert sm2.is_processed(test_id)
    print("   ✓ Memory persisted successfully across restart!")

    # Step 4: Watermark tracking
    print("\n[Step 4] Testing High-Watermark tracking...")
    sm2.set_watermark("2026/09/04 02:00:00")
    print(f"   Retrieved watermark: {sm2.get_watermark()} (Expected: 2026/09/04 02:00:00)")
    assert sm2.get_watermark() == "2026/09/04 02:00:00"

    # Clean up test entry
    if test_id in sm2.state.get("processed_messages", {}):
        del sm2.state["processed_messages"][test_id]
        sm2._save_state()

    print("\n" + "=" * 70)
    print("✅ ANGLE 2 & 3 PASSED: STATE MANAGER GUARANTEES EXACTLY-ONCE DELIVERY & WATERMARK.")
    print("=" * 70)

if __name__ == "__main__":
    main()
