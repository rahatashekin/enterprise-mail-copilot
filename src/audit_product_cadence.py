"""
Product & Cadence Frequency Audit
Enterprise Trading Corporation

Analyzes local powerplant_emails.json & attachments_manifest.json to extract:
  1. Month-by-month email & tender volume (Seasonality / Cadence)
  2. Top recurring product lines & spares
  3. Frequency of repeat requirements
"""

import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime
from email.utils import parsedate_to_datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EMAILS_FILE = DATA_DIR / "powerplant_emails.json"
MANIFEST_FILE = DATA_DIR / "attachments_manifest.json"
OUTPUT_FILE = DATA_DIR / "product_cadence_report.json"

PRODUCT_CATEGORIES = {
    "Gaskets & Seals": [
        r"gasket", r"seal ring", r"rubber sheet", r"o-ring", r"spiral wound",
        r"metallic gasket", r"profiled gasket", r"pressure seal"
    ],
    "Gland Packings & Ropes": [
        r"gland packing", r"packing rope", r"e-rope", r"ptfe packing",
        r"graphite packing", r"carbon packing"
    ],
    "Pumps & Spares": [
        r"pump", r"booster pump", r"submersible", r"impeller",
        r"mechanical seal", r"bearing"
    ],
    "Valves & Flow Control": [
        r"valve", r"gate valve", r"globe valve", r"check valve",
        r"safety valve", r"ball valve", r"actuator"
    ],
    "Fasteners & Hardware": [
        r"fastener", r"bolt", r"nut", r"washer", r"stud", r"screw"
    ],
    "Boiler & Turbine Internals": [
        r"boiler", r"turbine", r"shield", r"grating", r"tube",
        r"esp internal", r"air preheater"
    ],
    "Chemicals & Consumables": [
        r"chemical", r"loctite", r"corrosion inhibitor", r"preservation",
        r"lubricant", r"grease", r"welding", r"consumable"
    ],
    "Instrumentation & Electrical": [
        r"cable", r"sensor", r"transmitter", r"meter", r"gauge",
        r"calibration", r"switch", r"relay"
    ]
}

def parse_date(date_str):
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%Y-%m")
    except Exception:
        return None

def main():
    print("=" * 65)
    print("Enterprise Trading Corporation — PRODUCT & CADENCE AUDIT")
    print("=" * 65)

    if not EMAILS_FILE.exists():
        print(f"❌ Emails file not found at: {EMAILS_FILE}")
        sys.exit(1)

    with open(EMAILS_FILE, 'r', encoding='utf-8') as f:
        emails = json.load(f)

    print(f"📂 Analyzing {len(emails)} emails from local cache...\n")

    monthly_stats = defaultdict(lambda: {'incoming_powergen_a': 0, 'outgoing_powergen_a': 0, 'incoming_powergen_b': 0, 'outgoing_powergen_b': 0, 'total': 0})
    product_mentions = Counter()
    monthly_product_cadence = defaultdict(lambda: Counter())
    specific_products_list = []

    for e in emails:
        headers = e.get('headers', {})
        date_raw = headers.get('date', '')
        month_key = parse_date(date_raw)
        if not month_key:
            continue

        from_str = headers.get('from', '').lower()
        to_str = headers.get('to', '').lower()
        subj = headers.get('subject', '')
        body_snip = e.get('body', '')[:1000]
        full_text = f"{subj} {body_snip}".lower()

        # Track month cadence
        monthly_stats[month_key]['total'] += 1
        if 'energy-utility.com' in from_str: monthly_stats[month_key]['incoming_powergen_a'] += 1
        if 'energy-utility.com' in to_str: monthly_stats[month_key]['outgoing_powergen_a'] += 1
        if 'power-plant.gov.bd' in from_str: monthly_stats[month_key]['incoming_powergen_b'] += 1
        if 'power-plant.gov.bd' in to_str: monthly_stats[month_key]['outgoing_powergen_b'] += 1

        # Match product categories
        matched_cats = set()
        for cat, patterns in PRODUCT_CATEGORIES.items():
            for pat in patterns:
                if re.search(r'\b' + pat + r'\b', full_text):
                    matched_cats.add(cat)
                    product_mentions[cat] += 1
                    monthly_product_cadence[month_key][cat] += 1
                    break

    # Save to report
    sorted_months = sorted(monthly_stats.keys())
    report = {
        'monthly_cadence': {m: monthly_stats[m] for m in sorted_months},
        'product_distribution': dict(product_mentions.most_common()),
        'monthly_products': {m: dict(monthly_product_cadence[m]) for m in sorted_months}
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Print Table 1: Monthly Cadence
    print("=" * 70)
    print("📅 MONTH-BY-MONTH PROCUREMENT CADENCE (facility_a & facility_b)")
    print("=" * 70)
    print(f"{'Month':<10} {'powergen_a In':<12} {'powergen_a Out':<12} {'powergen_b In':<12} {'powergen_b Out':<12} {'Total Msgs':<10}")
    print("-" * 70)

    for m in sorted_months:
        st = monthly_stats[m]
        print(f"{m:<10} {st['incoming_powergen_a']:<12} {st['outgoing_powergen_a']:<12} {st['incoming_powergen_b']:<12} {st['outgoing_powergen_b']:<12} {st['total']:<10}")

    print("=" * 70)

    # Print Table 2: Product Breakdown
    print("\n" + "=" * 70)
    print("🏆 TOP PRODUCT LINES BY INQUIRY & TENDER FREQUENCY")
    print("=" * 70)
    total_mentions = sum(product_mentions.values()) or 1
    for cat, count in product_mentions.most_common():
        pct = round((count / total_mentions) * 100, 1)
        bar = "█" * int(pct // 3)
        print(f"{cat:<30} {count:<6} ({pct:>4}%) {bar}")

    print("=" * 70)
    print(f"\n✅ Full report saved to: {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
