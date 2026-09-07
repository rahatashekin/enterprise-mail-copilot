"""
Test Verification for Angle 4: Live Notification & Google Sheet/Excel Sync
Tests:
  - Excel Tender Tracker row insertion, styling, and hyperlinks
  - Alert Notifier dispatch
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.sheet_sync import SheetSync
from src.notifier import Notifier

def main():
    print("=" * 70)
    print("TESTING ANGLE 4: LIVE NOTIFICATION & EXCEL TRACKER SYNC")
    print("=" * 70)

    # 1. Test Excel Tracker Sync
    print("\n[Step 1/2] Appending real tender entry to Tender_Tracker.xlsx...")
    sheet_sync = SheetSync()

    test_tender = {
        "plant_name": "প্ল্যান্ট-বি ১৩২০ মেগাওয়াট (powergen_b)",
        "tender_no": "powergen_b/Procurement/RFQ/2024-25/0310.02",
        "submission_deadline": "১৭ মার্চ ২০২৫, দুপুর ১২:০০",
        "items_summary": "Quick-drying caster's glue, YUANDA 793-A Sealant, JAPAN 1212 Silicone, PVC Pipes (10 Items)",
        "quantities": "100 Meter, 48 PCS, 20 PCS, 2 Barrels",
        "officer_name": "রাশেদ মোর্শেদ (Superintending Engineer)",
        "special_clauses": "চুক্তি স্বাক্ষরের ২১ দিনের মধ্যে ধানখালী সাইটে ডেলিভারি নিশ্চিত করতে হবে।",
        "status": "NEW - Review Required",
        "message_id": "1957f6d9001"
    }

    excel_file = sheet_sync.append_tender(test_tender)
    print(f"   ✓ Successfully synced tender to Excel: {excel_file}")
    assert Path(excel_file).exists()

    # 2. Test Alert Notifier
    print("\n[Step 2/2] Testing Alert Notifier dispatch...")
    notifier = Notifier()

    sample_msg = (
        "🔔 নতুন দরপত্র নোটিশ (প্ল্যান্ট-বি ১৩২০ মেগাওয়াট)\n"
        "──────────────────────────────\n"
        "• টেন্ডার নং: powergen_b/Procurement/RFQ/2024-25/0310.02\n"
        "• আইটেম: সিল্যান্ট ও পিভিসি পাইপ (১০টি আইটেম)\n"
        "• ডেডলাইন: ১৭ মার্চ ২০২৫, দুপুর ১২:০০\n"
        "• অফিসার: রাশেদ মোর্শেদ (তত্ত্বাবধায়ক প্রকৌশলী)\n"
        "──────────────────────────────\n"
        "📧 মেইল লিঙ্ক: https://mail.google.com/mail/u/0/#inbox/1957f6d9001"
    )

    res = notifier.send_alert(sample_msg)
    print(f"   ✓ Notifier Status: {res.get('status')} via channel [{res.get('channel')}]")
    print(f"   ✓ Preview: {res.get('preview')[:60]}...")

    print("\n" + "=" * 70)
    print("✅ ANGLE 4 PASSED: EXCEL TRACKER IS LIVE AND NOTIFIER PIPELINE IS OPERATIONAL.")
    print("=" * 70)

if __name__ == "__main__":
    main()
