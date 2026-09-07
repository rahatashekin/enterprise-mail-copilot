"""
Step A1: Technical Variable Discovery & Pattern Mapping Audit
Enterprise Trading Corporation

Scans real downloaded files (PDF, Excel, Word) across the 5 procurement archetypes:
  1. RFQ / Tender Notices (PDF)
  2. BOQ & Pricing Schedules (Excel / PDF)
  3. Purchase Orders / Contracts (PDF)
  4. Delivery Challans & Shipping (PDF)
  5. Performance Guarantee (PG) & LC (PDF)

Discovers recurring clauses, key fields, and headers to build the Master Extraction Matrix.
"""

import os, json, re, sys
from pathlib import Path
from collections import defaultdict
import pypdf
import openpyxl

ATTACHMENTS_DIR = Path(r"D:\digital-corporation\attachments")
DATA_DIR = Path(r"C:\Users\Home\Documents\PythonProjects\digital-corporation\data")
OUTPUT_FILE = DATA_DIR / "variable_discovery_matrix.json"

ARCHETYPE_PATTERNS = {
    "1. RFQ & Tender Notice": [r"rfq", r"tender", r"nit", r"te_", r"enquiry", r"quotation"],
    "2. BOQ & Price Schedule": [r"boq", r"item details", r"details\.xlsx", r"schedule", r"consumable.*\.xlsx"],
    "3. Purchase Order & Award": [r"purchase order", r"po ", r"po_", r"noa", r"contract"],
    "4. Delivery & Inspection": [r"challan", r"delivery", r"shipping", r"bl\.pdf", r"wcc"],
    "5. PG, Bank Guarantee & LC": [r"pg ", r"pg_", r"guarantee", r"bank", r"lc ", r"pi "]
}

CLAUSE_PATTERNS = {
    "Tender_Reference_No": [
        r"(?:tender|enquiry|rfq|nit|ref)[\s\.:\-_]+(?:no|number)?[\s\.:]+([A-Z0-9\/\-_\.]{5,35})",
        r"(?:powergen_a|powergen_b)[\w\/\-_]{5,35}"
    ],
    "Submission_Deadline": [
        r"(?:submission|closing|last|opening)\s+(?:date|time|deadline)[\s\.:]+([^\n\r,;]{6,35})",
        r"(?:due\s+on|submit\s+by)[\s\.:]+([^\n\r,;]{6,35})"
    ],
    "Tender_Security_EMD": [
        r"(?:tender\s+security|earnest\s+money|emd|security\s+deposit)[\s\.:]+([^\n\r,;]{5,40})",
        r"(?:bank\s+guarantee|pay\s+order)\s+of\s+([^\n\r,;]{5,40})"
    ],
    "Delivery_Period": [
        r"(?:delivery|completion)\s+(?:period|time|schedule)[\s\.:]+([^\n\r,;]{5,40})",
        r"within\s+(\d+\s+(?:days|weeks|months))"
    ],
    "Delivery_Location": [
        r"(?:delivery\s+at|destination|consignee|place\s+of\s+delivery)[\s\.:]+([^\n\r,;]{5,50})",
        r"(?:mstpp|facility_a|facility_b|bagerhat|patuakhali)"
    ],
    "Liquidated_Damages_Penalty": [
        r"(?:liquidated\s+damages|ld\s+clause|penalty)[\s\.:]+([^\n\r,;]{5,50})",
        r"(\d+(?:\.\d+)?%\s+per\s+week)"
    ],
    "Payment_Terms": [
        r"(?:payment\s+terms|mode\s+of\s+payment)[\s\.:]+([^\n\r,;]{5,60})",
        r"(?:letter\s+of\s+credit|lc|after\s+delivery|within\s+\d+\s+days\s+of\s+submission)"
    ],
    "Warranty_Period": [
        r"(?:warranty|guarantee)[\s\.:]+([^\n\r,;]{5,40})",
        r"(\d+\s+months\s+(?:from|after))"
    ]
}

def extract_text_from_pdf(filepath, max_pages=3):
    text = ""
    try:
        reader = pypdf.PdfReader(str(filepath))
        for i in range(min(len(reader.pages), max_pages)):
            page_text = reader.pages[i].extract_text() or ""
            text += page_text + "\n"
    except Exception as e:
        pass
    return text

def inspect_excel(filepath):
    details = {}
    try:
        wb = openpyxl.load_workbook(str(filepath), read_only=True, data_only=True)
        details["sheet_names"] = wb.sheetnames
        ws = wb.active
        headers = []
        for row in ws.iter_rows(max_row=5, values_only=True):
            non_empty = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
            if len(non_empty) >= 3:
                headers = non_empty
                break
        details["detected_columns"] = headers[:10]
    except Exception as e:
        details["error"] = str(e)
    return details

def main():
    print("=" * 70)
    print("Enterprise Trading Corporation — STEP A1: TECHNICAL VARIABLE DISCOVERY")
    print("=" * 70)

    if not ATTACHMENTS_DIR.exists():
        print(f"❌ Attachments directory not found: {ATTACHMENTS_DIR}")
        sys.exit(1)

    all_files = list(ATTACHMENTS_DIR.glob("*.*"))
    print(f"📁 Scanning {len(all_files)} documents on disk...\n")

    # Group files by archetype
    categorized = defaultdict(list)
    for f in all_files:
        fn_lower = f.name.lower()
        matched = False
        for arc, patterns in ARCHETYPE_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, fn_lower):
                    categorized[arc].append(f)
                    matched = True
                    break
            if matched:
                break
        if not matched:
            categorized["6. General Technical Specs"].append(f)

    print("📊 ARCHETYPE DISTRIBUTION:")
    for arc, files in sorted(categorized.items()):
        print(f"  • {arc:<30} : {len(files):>4} files")

    print("\n" + "=" * 70)
    print("🔬 DEEP SCANNING REPRESENTATIVE FILES FOR VARIABLES & HEADERS")
    print("=" * 70)

    archetype_findings = {}

    for arc, files in sorted(categorized.items()):
        print(f"\n📂 Investigating Archetype: [{arc}]")
        sample_files = files[:4]
        arc_data = {
            "total_files": len(files),
            "sampled_files": [],
            "detected_variables": defaultdict(int),
            "sample_evidence": {}
        }

        for sf in sample_files:
            ext = sf.suffix.lower()
            file_summary = {"file_name": sf.name, "extension": ext, "size_kb": sf.stat().st_size // 1024}

            if ext == ".pdf":
                raw_text = extract_text_from_pdf(sf, max_pages=4)
                file_summary["text_extracted_chars"] = len(raw_text)

                # Test for key clauses
                for clause_name, patterns in CLAUSE_PATTERNS.items():
                    for pat in patterns:
                        match = re.search(pat, raw_text, re.IGNORECASE)
                        if match:
                            arc_data["detected_variables"][clause_name] += 1
                            if clause_name not in arc_data["sample_evidence"]:
                                arc_data["sample_evidence"][clause_name] = match.group(0).strip().replace('\n', ' ')
                            break

            elif ext in [".xlsx", ".xls"]:
                xl_info = inspect_excel(sf)
                file_summary["excel_structure"] = xl_info
                for col in xl_info.get("detected_columns", []):
                    arc_data["detected_variables"][f"Excel_Col: {col}"] += 1

            arc_data["sampled_files"].append(file_summary)
            print(f"   ✓ Scanned: {sf.name[:45]:<45} ({file_summary['size_kb']} KB)")

        archetype_findings[arc] = arc_data

    # Compile the Master Variable Matrix
    master_matrix = {
        "mandatory_variables": [
            {"variable": "Tender_Reference_No", "importance": "CRITICAL", "description": "অফিসিয়াল দরপত্র / নোটিশ নম্বর"},
            {"variable": "Client_Plant_Name", "importance": "CRITICAL", "description": "প্ল্যান্ট-বি (powergen_b) নাকি প্ল্যান্ট-এ (powergen_a)"},
            {"variable": "Submission_Deadline", "importance": "CRITICAL", "description": "দরপত্র জমা দেওয়ার শেষ সময় ও তারিখ"},
            {"variable": "Target_Items_List", "importance": "CRITICAL", "description": "পণ্যের নাম, স্পেসিফিকেশন, মেটেরিয়াল ও সাইজ"},
            {"variable": "Item_Quantities_and_Units", "importance": "CRITICAL", "description": "পরিমাণ ও একক (e.g. 20 Pcs, 100 Meter)"},
            {"variable": "Issuing_Officer_Contact", "importance": "HIGH", "description": "সংশ্লিষ্ট ইঞ্জিনিয়ারের নাম, পদবি ও ইমেইল"}
        ],
        "situational_variables": [
            {"variable": "Delivery_Period", "condition": "When specified in RFQ / PO", "description": "কত দিনের মধ্যে মাল ডেলিভারি দিতে হবে (e.g. 30 Days)"},
            {"variable": "Delivery_Location", "condition": "When specified", "description": "সাইটের সুনির্দিষ্ট ডেলিভারি পয়েন্ট (BMD Store, C&I Store)"},
            {"variable": "Tender_Security_EMD", "condition": "Big tenders (>10 Lac)", "description": "জামানত / পে-অর্ডারের পরিমাণ বা ব্যাংক গ্যারান্টি শর্ত"},
            {"variable": "Payment_Terms", "condition": "PO / Contract Stage", "description": "এলসি শর্ত নাকি ডেলিভারির পর বিল পরিশোধ"},
            {"variable": "Liquidated_Damages", "condition": "PO / Contract Stage", "description": "বিলম্বিত ডেলিভারির জন্য জরিমানার শর্ত (LD Clause)"},
            {"variable": "Warranty_Period", "condition": "Equipment / Spares", "description": "ওয়ারেন্টির মেয়াদ (১২ বা ১৮ মাস)"},
            {"variable": "Previous_Quote_Context", "condition": "Ongoing Negotiation", "description": "মামার আগের কোটেশন রেফারেন্স ও বায়ারের নতুন অফার"}
        ],
        "archetype_scans": archetype_findings
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(master_matrix, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("📋 MASTER EXTRACTION MATRIX SUMMARY")
    print("=" * 70)
    print("\n🔴 MANDATORY VARIABLES (সব মেইলে অবশ্যই থাকবে):")
    for item in master_matrix["mandatory_variables"]:
        print(f"  • {item['variable']:<30} [{item['importance']}] : {item['description']}")

    print("\n🟡 SITUATIONAL VARIABLES (পরিস্থিতি ও স্টেজ অনুযায়ী কম-বেশি হবে):")
    for item in master_matrix["situational_variables"]:
        print(f"  • {item['variable']:<30} [Condition: {item['condition']}] : {item['description']}")

    print("\n" + "=" * 70)
    print(f"✅ Full variable matrix saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
