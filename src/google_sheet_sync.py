"""
Google Sheet Sync — Cloud-Based Live Tracker (v2 — Tier-Specific Tabs)
Enterprise Trading Corporation — Business Mail Copilot

Syncs extracted email data to Google Sheets in real-time using
a Service Account. Maintains four worksheets:
  1. 🏭 দরপত্র ও কার্যাদেশ — Buyer pipeline (RFQ → PO → Delivery → Payment)
  2. 📦 সরবরাহকারী — Supplier quotes and negotiations
  3. 🏦 ব্যাংকিং — LC, SWIFT, TT tracking
  4. ⏰ টাইমলাইন — Chronological event log for all tiers

Uses gspread library with Service Account authentication.
"""

import gspread
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SA_FILE = PROJECT_ROOT / "config" / "service_account.json"

# Live Google Sheet ID
SHEET_ID = os.environ.get('GOOGLE_SHEET_ID', '')
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"

# Tab names
TAB_BUYER = "🏭 দরপত্র ও কার্যাদেশ"
TAB_SUPPLIER = "📦 সরবরাহকারী"
TAB_BANK = "🏦 ব্যাংকিং"
TAB_TIMELINE = "⏰ টাইমলাইন"

# Stage display names (Bengali)
STAGE_DISPLAY = {
    "1_NEW_RFQ": "নতুন দরপত্র",
    "2_NEGOTIATION": "আলোচনা/দরকষাকষি",
    "3_PO_AWARD": "কার্যাদেশ প্রাপ্ত",
    "4_DELIVERY_CHALLAN": "পণ্য সরবরাহ",
    "5_PG_PAYMENT": "পেমেন্ট/গ্যারান্টি",
    "S1_QUOTE_RECEIVED": "কোটেশন প্রাপ্ত",
    "S2_UNDER_REVIEW": "কোটেশন রিভিউ",
    "S3_ORDER_PLACED": "অর্ডার প্রদান",
    "S4_AWAITING_DELIVERY": "ডেলিভারি অপেক্ষমান",
    "B1_LC_DRAFT": "এলসি ড্রাফট",
    "B2_LC_OPENED": "এলসি ওপেন",
    "B3_DOCS_SUBMITTED": "ডকুমেন্ট জমা",
    "B4_PAYMENT_RECEIVED": "পেমেন্ট প্রাপ্ত",
}

TIER_EMOJI = {
    "BUYER": "🏭",
    "SUPPLIER": "📦",
    "BANK": "🏦",
}


class GoogleSheetSync:
    """Real-time sync to Google Sheets via Service Account."""

    def __init__(self, sheet_id: str = SHEET_ID, sa_file: Path = SA_FILE):
        self.gc = gspread.service_account(filename=str(sa_file))
        self.spreadsheet = self.gc.open_by_key(sheet_id)
        self.sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"

    def sync_event(
        self,
        extracted_data: Dict[str, Any],
        project_summary: Dict[str, Any] = None,
        message_id: str = "",
        thread_id: str = "",
        tier: str = "BUYER",
        source_domain: str = "",
    ):
        """
        Main sync method — routes to tier-specific tab + appends Timeline.
        """
        if project_summary is None:
            project_summary = {}

        stage = extracted_data.get("lifecycle_stage", "1_NEW_RFQ")
        stage_display = STAGE_DISPLAY.get(stage, stage)
        gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{message_id}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        proj_id = extracted_data.get("project_id") or project_summary.get("project_id", "")

        # Route to tier-specific tab
        if tier == "BUYER":
            self._upsert_buyer(proj_id, extracted_data, stage_display, gmail_link, now_str)
        elif tier == "SUPPLIER":
            self._upsert_supplier(proj_id, extracted_data, stage_display, gmail_link, now_str)
        elif tier == "BANK":
            self._upsert_bank(proj_id, extracted_data, stage_display, gmail_link, now_str)

        # Always append to Timeline
        self._append_timeline(
            proj_id=proj_id,
            extracted_data=extracted_data,
            stage_display=stage_display,
            gmail_link=gmail_link,
            tier=tier,
        )

    # ─────────────────────────────────────────────
    # 🏭 BUYER TAB
    # ─────────────────────────────────────────────
    def _upsert_buyer(self, proj_id, data, stage_display, gmail_link, now_str):
        """Upsert a row in the Buyer Pipeline tab."""
        ws = self.spreadsheet.worksheet(TAB_BUYER)

        row = [
            "",  # ক্রম
            proj_id,
            data.get("project_title", ""),
            data.get("plant_name", ""),
            stage_display,
            data.get("tender_no", "") or "",
            data.get("po_number", "") or "",
            data.get("total_contract_value", "") or "",
            data.get("tender_security_emd", "") or "",
            data.get("submission_deadline", "") or "",
            data.get("delivery_deadline", "") or data.get("delivery_period", "") or "",
            str(data.get("items_specs", "") or data.get("items_ordered", "") or "")[:300],
            data.get("payment_lc_terms", "") or data.get("payment_terms", "") or "",
            data.get("warranty_period", "") or "",
            str(data.get("critical_action", ""))[:300],
            data.get("issuing_officer", "") or "",
            now_str,
            gmail_link,
            data.get("buyer_contact_person", "") or "",
            data.get("prebid_meeting_date", "") or "",
            data.get("tax_vat_details", "") or "",
            data.get("performance_guarantee_pct", "") or "",
        ]

        self._upsert_row(ws, proj_id, row, col_count=22)

    # ─────────────────────────────────────────────
    # 📦 SUPPLIER TAB
    # ─────────────────────────────────────────────
    def _upsert_supplier(self, proj_id, data, stage_display, gmail_link, now_str):
        """Upsert a row in the Supplier Tracker tab."""
        ws = self.spreadsheet.worksheet(TAB_SUPPLIER)

        row = [
            "",  # ক্রম
            proj_id,
            data.get("supplier_name", "") or "",
            stage_display,
            str(data.get("quoted_items", "") or data.get("items_summary", "") or "")[:300],
            data.get("total_quoted_amount", "") or "",
            data.get("unit_price_breakdown", "") or data.get("unit_prices", "") or "",
            data.get("validity_period", "") or data.get("quote_validity", "") or data.get("offer_validity", "") or "",
            data.get("delivery_terms", "") or data.get("delivery_lead_time", "") or data.get("delivery_timeline", "") or "",
            data.get("related_tender_ref", "") or "",
            str(data.get("critical_action", ""))[:300],
            data.get("supplier_contact", "") or data.get("contact_person", "") or "",
            now_str,
            gmail_link,
            data.get("supplier_country", "") or "",
            data.get("incoterms", "") or "",
            data.get("currency", "") or "",
            data.get("proforma_invoice_no", "") or "",
        ]

        self._upsert_row(ws, proj_id, row, col_count=18)

    # ─────────────────────────────────────────────
    # 🏦 BANK TAB
    # ─────────────────────────────────────────────
    def _upsert_bank(self, proj_id, data, stage_display, gmail_link, now_str):
        """Upsert a row in the Banking tab."""
        ws = self.spreadsheet.worksheet(TAB_BANK)

        row = [
            "",  # ক্রম
            proj_id,
            data.get("bank_name", "") or "",
            stage_display,
            data.get("document_type", "") or "",
            data.get("lc_number", "") or data.get("swift_ref", "") or "",
            data.get("lc_amount", "") or data.get("amount", "") or data.get("transaction_amount", "") or "",
            data.get("beneficiary_name", "") or data.get("beneficiary", "") or "",
            data.get("lc_expiry", "") or data.get("expiry_date", "") or "",
            data.get("related_project", "") or data.get("related_tender_ref", "") or data.get("related_po", "") or "",
            str(data.get("critical_action", ""))[:300],
            now_str,
            gmail_link,
            data.get("lc_type", "") or "",
            data.get("documents_required", "") or "",
            data.get("tt_reference_no", "") or "",
        ]

        self._upsert_row(ws, proj_id, row, col_count=16)

    # ─────────────────────────────────────────────
    # ⏰ TIMELINE TAB (append-only)
    # ─────────────────────────────────────────────
    def _append_timeline(self, proj_id, extracted_data, stage_display, gmail_link, tier):
        """Append a new row to the Timeline worksheet."""
        ws = self.spreadsheet.worksheet(TAB_TIMELINE)

        # Email date from extracted data
        email_date = extracted_data.get("email_date", "") or ""

        # Sender — tier-aware
        sender = (
            extracted_data.get("issuing_officer")
            or extracted_data.get("supplier_name")
            or extracted_data.get("bank_name")
            or ""
        )

        all_rows = ws.get_all_values()
        new_sl = len(all_rows)  # header is row 1

        tier_emoji = TIER_EMOJI.get(tier, tier)

        event_row = [
            new_sl,
            email_date,
            tier_emoji,
            proj_id,
            str(sender)[:100],
            stage_display,
            str(extracted_data.get("critical_action", ""))[:200],
            gmail_link,
        ]

        ws.append_row(event_row, value_input_option="USER_ENTERED")

    # ─────────────────────────────────────────────
    # SHARED: Upsert by Project ID (column B)
    # ─────────────────────────────────────────────
    def _upsert_row(self, ws, proj_id, row_values, col_count):
        """Find existing row by Project ID (col B) and update, or append."""
        # Search for existing row
        try:
            cell = ws.find(proj_id, in_column=2)
            row_num = cell.row if cell else None
        except Exception:
            row_num = None

        # Column letter for the last column
        last_col = chr(64 + col_count)  # 18 -> R, 14 -> N, 13 -> M

        if row_num:
            # Update existing row (skip Sl column A)
            ws.update(
                values=[row_values[1:]],
                range_name=f"B{row_num}:{last_col}{row_num}"
            )
        else:
            # Append new row with auto Sl
            all_values = ws.get_all_values()
            new_sl = len(all_values)  # header=1, first data=1
            row_values[0] = new_sl
            ws.append_row(row_values, value_input_option="USER_ENTERED")

    def get_sheet_url(self) -> str:
        """Return the live Google Sheet URL for WhatsApp messages."""
        return self.sheet_url
