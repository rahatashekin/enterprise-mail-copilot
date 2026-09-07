"""
Enterprise Trading Corporation — Master Autonomous Tender Copilot Worker (Dynamic SS2 Lifecycle Engine)
Unified 24/7 Worker Engine:
  - 5-Stage Dynamic Lifecycle Variable Extraction matching SS2:
      1_NEW_RFQ: টেন্ডার রেফারেন্স, আইটেম ও স্পেক্স, জমার ডেডলাইন, টেন্ডার সিকিউরিটি (EMD), ডেলিভারির সময়সীমা
      2_NEGOTIATION: বায়ারের আপত্তি, ডিসকাউন্ট দাবি, সময়সীমার চাপ, পালটা অফার
      3_PO_AWARD: পারচেজ অর্ডার নম্বর, মোট টাকার অংক (BDT/USD), পেমেন্ট / এলসি শর্ত, ওয়ারেন্টি পিরিয়ড
      4_DELIVERY_CHALLAN: চালান নম্বর, ডেলিভারি লোকেশন, ইন্সপেকশন তারিখ
      5_PG_PAYMENT: ব্যাংক গ্যারান্টি নং, জামানতের অংক, রিলিজের মেয়াদ
  - SS1-Compliant Executive WhatsApp Formatter
  - In-Memory Document Unpacker (PDF, Excel, Word, ZIP)
  - Bi-Directional Dialogue History Assembler
  - Live Excel Tracker Synchronization
  - Multi-Channel Notifier
  - Atomic State Idempotency
"""

import os, json, time, sys
from pathlib import Path
from typing import Dict, Any, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.document_unpacker import DocumentUnpacker
from src.state_manager import StateManager
from src.sheet_sync import SheetSync
from src.notifier import Notifier
from src.tender_parser import ContextAssembler, WhatsAppFormatter
from src.project_graph import ProjectGraph
from src.domain_router import DomainRouter
from src.google_sheet_sync import GoogleSheetSync

from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
TOKEN_FILE = CONFIG_DIR / "gmail_token.json"
GEMINI_KEY_FILE = CONFIG_DIR / "gemini_api_key.txt"
EMAILS_CACHE = DATA_DIR / "powerplant_emails.json"

class TenderCopilotWorker:
    """Production Autonomous Pipeline with Dynamic SS2 Lifecycle Extraction and Cross-Thread Memory."""

    def __init__(self):
        self.state_mgr = StateManager()
        self.sheet_sync = SheetSync()
        self.notifier = Notifier()
        self.project_graph = ProjectGraph()
        self.domain_router = DomainRouter()
        self.google_sheet = GoogleSheetSync()

        # Load Gemini API Key
        gemini_key = ""
        if GEMINI_KEY_FILE.exists():
            gemini_key = GEMINI_KEY_FILE.read_text(encoding="utf-8").strip()
        self.gemini_client = genai.Client(api_key=gemini_key) if gemini_key else None

        # Load Gmail Credentials
        if TOKEN_FILE.exists():
            token_data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
            creds = Credentials(
                token=token_data.get('access_token') or token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.environ.get('GMAIL_CLIENT_ID'),
                client_secret=os.environ.get('GMAIL_CLIENT_SECRET'),
            )
            self.gmail_service = build('gmail', 'v1', credentials=creds)
        else:
            self.gmail_service = None

    def process_message(self, message_id: str, email_obj: Dict[str, Any], attachment_files: List[Path] = None, dialogue_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes end-to-end pipeline on a single email.
        Guarantees idempotency and resolves cross-thread project memory.
        """
        if self.state_mgr.is_processed(message_id):
            return {"status": "skipped", "reason": "Already processed (Idempotent lock)"}

        thread_id = email_obj.get("thread_id", "")
        headers = email_obj.get("headers", {})
        subj = headers.get("subject", "No Subject")
        sender = headers.get("from", "")
        body_text = email_obj.get("body", "")

        # 0. Domain Router — Classify email tier before processing
        routing = self.domain_router.classify(sender, subj)
        tier = routing["tier"]
        source_domain = routing["domain"]

        if tier == "IGNORE":
            self.state_mgr.mark_completed(message_id, thread_id, {"status": "ignored", "tier": tier, "reason": routing["confidence"]})
            return {"status": "skipped", "reason": f"Domain routing: {routing['confidence']}", "tier": tier, "domain": source_domain}

        # 1. Autonomous Cross-Thread Resolution via ProjectGraph
        proj_id, is_new_proj = self.project_graph.resolve_or_create_project(email_obj, tier=tier, source_domain=source_domain)
        auto_cross_history = self.project_graph.get_cross_thread_history(proj_id, exclude_message_id=message_id)
        active_history = auto_cross_history if auto_cross_history else (dialogue_history or [])
        proj_summary = self.project_graph.get_project_summary(proj_id) or {}

        # 2. Unpack all attached documents (including inner ZIP files)
        unpacked_items = []
        if attachment_files:
            for af in attachment_files:
                unpacked_items.extend(DocumentUnpacker.unpack_and_extract(af))

        # 3. Tier-Routed AI Extraction via Gemini
        if tier == "BUYER":
            extracted_data = self._run_dynamic_gemini_extraction(email_obj, unpacked_items, active_history, proj_summary)
        elif tier == "SUPPLIER":
            extracted_data = self._run_supplier_extraction(email_obj, unpacked_items, proj_summary, active_history)
        elif tier == "BANK":
            extracted_data = self._run_bank_extraction(email_obj, unpacked_items, proj_summary, active_history)
        elif tier == "INTERNAL":
            extracted_data = self._run_dynamic_gemini_extraction(email_obj, unpacked_items, active_history, proj_summary)
        else:
            extracted_data = self._run_dynamic_gemini_extraction(email_obj, unpacked_items, active_history, proj_summary)
        stage = extracted_data.get("lifecycle_stage", "1_NEW_RFQ")

        # Reference fallback: if tender_no is long, missing, or raw text, use dossier tender_no
        ext_tender = str(extracted_data.get("tender_no", "")).strip()
        if (not ext_tender or ext_tender == "N/A" or len(ext_tender) > 40 or "regarding" in ext_tender.lower()):
            if proj_summary.get("tender_no") and proj_summary.get("tender_no") != "N/A":
                extracted_data["tender_no"] = proj_summary.get("tender_no")

        # 4. Record event into Project Dossier Timeline
        summary_txt = extracted_data.get("critical_action") or subj
        is_out = ("enterprise.automation@example.com" in sender.lower() or "lead" in sender.lower())
        self.project_graph.record_event(
            project_id=proj_id,
            thread_id=thread_id,
            message_id=message_id,
            timestamp=headers.get("date", ""),
            sender=sender,
            is_outgoing=is_out,
            stage=stage,
            summary_text=summary_txt[:300],
            extracted_data=extracted_data
        )

        proj_summary = self.project_graph.get_project_summary(proj_id) or {}
        extracted_data["project_id"] = proj_id
        extracted_data["project_title"] = proj_summary.get("title", subj)
        extracted_data["linked_threads_count"] = proj_summary.get("total_linked_threads", 1)
        extracted_data["email_date"] = email_obj.get('headers', {}).get('date', '')

        # 5. Context Packet for Formatter
        context_packet = {
            "current_message_id": message_id,
            "thread_id": thread_id,
            "project_id": proj_id,
            "subject": subj,
            "current_sender": sender,
            "current_body": body_text,
            "email_date": email_obj.get('headers', {}).get('date', ''),
            "turn_number": proj_summary.get("total_events", 1),
            "dialogue_history": active_history
        }

        # 6. Sync to Excel Tracker (Master Pipeline Upsert + Event Log Append)
        self.sheet_sync.sync_event(
            extracted_data=extracted_data,
            project_summary=proj_summary,
            message_id=message_id,
            thread_id=thread_id,
            tier=tier,
            source_domain=source_domain
        )

        # 6b. Sync to Google Sheets (Cloud Live Tracker)
        try:
            self.google_sheet.sync_event(
                extracted_data=extracted_data,
                project_summary=proj_summary,
                message_id=message_id,
                thread_id=thread_id,
                tier=tier,
                source_domain=source_domain
            )
        except Exception as e:
            # Google Sheet sync failure should not block the pipeline
            pass

        # 7. Format & Dispatch Executive WhatsApp Alert (SS1 Format)
        context_packet["sheet_url"] = self.google_sheet.get_sheet_url()
        alert_msg = WhatsAppFormatter.format_alert(stage, extracted_data, context_packet)
        dispatch_res = self.notifier.send_alert(alert_msg)

        # 8. Mark as permanently completed in State Manager
        self.state_mgr.mark_completed(message_id, thread_id, extracted_data)

        return {
            "status": "completed",
            "message_id": message_id,
            "project_id": proj_id,
            "lifecycle_stage": stage,
            "extracted_data": extracted_data,
            "alert_message": alert_msg,
            "dispatch": dispatch_res
        }

    def _run_dynamic_gemini_extraction(self, email_obj: Dict[str, Any], unpacked_items: List[Dict[str, Any]], dialogue_history: List[Dict[str, Any]] = None, project_summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dynamic SS2-Compliant Variable Extraction Engine."""
        headers = email_obj.get('headers', {})
        sender = headers.get('from', '')
        subj = headers.get('subject', '')
        body_snippet = email_obj.get('body', '')

        is_outgoing = "enterprise.automation@example.com" in sender.lower() or "lead" in sender.lower()
        plant_guess = "প্ল্যান্ট-এ পাওয়ার প্ল্যান্ট (powergen_a)" if "powergen_a" in str(email_obj).lower() else "প্ল্যান্ট-বি পাওয়ার প্ল্যান্ট (powergen_b)"

        default_data = {
            "lifecycle_stage": "1_NEW_RFQ",
            "plant_name": plant_guess,
            "tender_no": "N/A",
            "critical_action": "ইমেইল ও সংযুক্ত নথি পর্যালোচনা করে প্রয়োজনীয় ব্যবস্থা গ্রহণ করুন।",
            "items_summary": subj,
            "message_id": email_obj.get("id", "")
        }

        if not self.gemini_client:
            return default_data

        # Build Dossier Context if available
        dossier_ctx = ""
        dossier_tender_no = ""
        if project_summary:
            dossier_tender_no = project_summary.get("tender_no", "")
            dossier_lines = ["\n[PROJECT DOSSIER MEMORY (ACID SQLite)]"]
            if project_summary.get("title"):
                dossier_lines.append(f"- Project Title: {project_summary.get('title')}")
            if dossier_tender_no and dossier_tender_no != "N/A":
                dossier_lines.append(f"- Official Tender/RFQ No: {dossier_tender_no}")
            if project_summary.get("po_no") and project_summary.get("po_no") != "N/A":
                dossier_lines.append(f"- Purchase Order (PO) No: {project_summary.get('po_no')}")
            if project_summary.get("contract_value") and project_summary.get("contract_value") != "N/A":
                dossier_lines.append(f"- Total Contract Value: {project_summary.get('contract_value')}")
            if project_summary.get("payment_terms") and project_summary.get("payment_terms") != "N/A":
                dossier_lines.append(f"- Contract Payment Terms: {project_summary.get('payment_terms')}")
            dossier_ctx = "\n".join(dossier_lines)

        # Build full conversational history text if available
        history_str = ""
        if dialogue_history:
            history_lines = ["\n[PRIOR CONVERSATION HISTORY (CHRONOLOGICAL)]"]
            for h in dialogue_history:
                history_lines.append(f"- Turn {h.get('turn')} [{h.get('party')} | {h.get('date')}]: {h.get('snippet')[:250]}...")
            history_str = "\n".join(history_lines)

        prompt = f"""
You are the Chief Commercial Officer & Procurement AI for Enterprise Trading Corporation (Vendor/Supplier).
Analyze this email and all attached documents thoroughly.

Email Subject: {subj}
Email Sender: {sender}
Is Sent By Enterprise Solutions (Vendor Outgoing): {is_outgoing}
Email Body:
{body_snippet}
{history_str}
{dossier_ctx}

MANDATORY CORPORATE LANGUAGE RULE: All extracted descriptive values, deadlines, notes, status descriptions, and instructions MUST be in professional formal Bengali (বাংলা). English is permitted ONLY for technical part codes, catalog numbers, brand/model names, emails, URLs, and currency symbols (e.g. BDT, USD). NEVER output generic English fallback phrases such as 'Not specified', 'Not applicable', 'None', or 'Immediate action recommended'—always use standard Bengali equivalents (e.g. 'বিজ্ঞপ্তিতে সুনির্দিষ্ট নয়', 'প্রযোজ্য নয় (বাজেটারি অফার)', 'জরুরি ভিত্তিতে প্রেরণ বাঞ্ছনীয়').
NATURAL BENGALI TIME FORMAT RULE: When writing submission deadlines or meeting times in Bengali, use standard natural 12-hour phrasing with time of day (e.g. 'দুপুর ২:৩০', 'বিকাল ৫:০০', 'সকাল ১০:০০', 'রাত ৮:০০'). NEVER mix 24-hour military numbers with period words (e.g. do NOT write 'দুপুর ১৪:৩০' or 'বিকাল ১৭:০০').

TASK:
1. IDENTIFY THE EXACT LIFECYCLE STAGE (Must be exactly one of these 5):
   - "1_NEW_RFQ": Buyer/Plant is issuing a fresh tender enquiry, invitation for bids, or RFQ.
   - "2_NEGOTIATION": Ongoing dialogue discussing price justification, discounts, technical clarification, meeting calls, or corrigendum.
   - "3_PO_AWARD": Formal Purchase Order (PO), Work Order, or Notification of Award (NOA) issued to Enterprise Solutions.
   - "4_DELIVERY_CHALLAN": Vendor/Enterprise Solutions is sending goods delivery info, challan, packing list, or tracking site handover.
   - "5_PG_PAYMENT": Performance Guarantee (PG), Bank Guarantee, security deposit release request, or bill payment follow-up.

2. EXTRACT COMMON FIELDS (always extract regardless of stage):
   - buyer_contact_person: Email sender's full name, designation/title, mobile number, and email address. Extract from email signature or headers.

3. DYNAMICALLY EXTRACT THE EXACT STAGE-SPECIFIC VARIABLES (Based on the detected stage):
   - IF 1_NEW_RFQ:
       * tender_no: Exact Tender/RFQ Ref (e.g. Plant/Dept/Year/Ref). If there is no formal tender number in the notice, accurately describe the type of enquiry in formal Bengali (e.g. 'প্রযোজ্য নয় (শর্টলিস্টিং ক্রেডেনশিয়াল আহ্বান)' for credential shortlisting; 'প্রযোজ্য নয় (বাজেটারি অনুসন্ধান)' for budgetary quotation; or 'বিজ্ঞপ্তিতে সুনির্দিষ্ট নয়').
       * items_specs: MANDATORY BOQ EXTRACTION RULE: You MUST scan all attached documents and email text/tables for the "Schedule of Requirements", "BOQ", or item lists. DO NOT just copy the package title. Extract every single line item with its item name, part/catalog number, quantity, and unit as a numbered list (e.g. "১. [Item Name] (Model/Part No: XYZ-101) - [Qty] [Unit]; ২. [Item Name] (P/N: ABC-202) - [Qty] [Unit]").
       * submission_deadline: Exact submission date & time in BST (in Bengali, e.g. '১১ মে ২০২৬, বিকাল ৫:০০'). If not stated, write 'বিজ্ঞপ্তিতে সুনির্দিষ্ট নয় (জরুরি ভিত্তিতে প্রেরণ বাঞ্ছনীয়)'.
       * tender_security_emd: Must include the exact monetary amount in standard comma-separated format (e.g. "BDT ৭০,০০০/-" or "BDT 70,000/-"), acceptable payment instrument(s) (Pay Order / Bank Draft / Bank Guarantee), and beneficiary name (e.g. "BDT [Amount]/- (পে-অর্ডার/ব্যাংক ড্রাফট - '[Beneficiary Organization]'-এর অনুকূলে)"). If budgetary or not required, write 'প্রযোজ্য নয় (বাজেটারি অফার)'.
       * delivery_period: Required delivery timeline from placement of purchase order (in Bengali, e.g. 'কার্যাদেশ প্রাপ্তির ৩০ দিনের মধ্যে'). If not stated, write 'বিজ্ঞপ্তিতে সুনির্দিষ্ট নয়'.
       * issuing_officer: Issuing officer name, designation, and mobile/email contact.
       * prebid_meeting_date: Pre-bid meeting/conference date, time, and venue (if mentioned in tender document). If not applicable, write 'প্রযোজ্য নয়'.
   - IF 2_NEGOTIATION:
       * tender_no: Package reference. If the incoming email body lacks a formal tender code, DO NOT put long email subject lines into tender_no. Use the Project Dossier's tender number: '{dossier_tender_no}'.
       * buyer_objection: Buyer's exact objection, query, or price justification requirement. If this is a tender amendment/corrigendum, summarize the core amendment subject.
       * discount_demand: Specific discount demanded, or if this is an amendment/corrigendum, state the exact changed terms/specifications (e.g. 'সরবরাহের সময়সীমা ৩০ দিন হতে ৪৫ দিন বৃদ্ধি এবং আইটেম-১ এ Accord/Alliance শর্ত প্রত্যাহার').
       * deadline_pressure: Urgency / reply deadline. Must be an exact calendar date in natural Bengali 12-hour format (e.g. '১৮ আগস্ট ২০২৬, বিকাল ৩:০০') or a concise 2-4 word urgency tag.
       * recommended_counter: Concise 1-2 sentence high-level tactical posture or compliance approach.
   - IF 3_PO_AWARD:
       * po_number: Official Purchase Order / NOA number.
       * total_contract_value: Total monetary value with currency.
       * items_ordered: Itemized list of awarded items and quantities (e.g. '১. [Item] - [Qty], ২. [Item] - [Qty]'). If the NOA/PO document only states the overall procurement package title, cross-reference the Project Dossier's prior item list and state the concise itemized items and quantities rather than just copying a long generic package title.
       * payment_lc_terms: Payment terms (e.g. advance %, delivery %, retention %, tax/VAT requirements).
       * warranty_period: Warranty term.
       * delivery_deadline: Final delivery date. If stated as a duration from placement/issue of PO (e.g. '2 months from PO date 03-Dec-2023'), calculate and explicitly state the exact calendar date (e.g. '০৩ ফেব্রুয়ারি ২০২৪ (ইস্যুর তারিখ হতে ৬০ দিন)').
   - IF 4_DELIVERY_CHALLAN:
       * challan_number: Challan / Dispatch note number & date.
       * po_reference: Associated Purchase Order number.
       * dispatched_items: Items and exact quantities delivered.
       * delivery_site: Delivery destination / warehouse location.
       * inspection_status: Status of site inspection / receiving.
   - IF 5_PG_PAYMENT:
       * project_tender_id: Associated Tender / PO / E-GP ID. If the email doesn't explicitly state the tender number, use the Project Dossier's tender number: '{dossier_tender_no}'.
       * bg_number: Bank Guarantee number if applicable, or omit if pure bill follow-up or pay order.
       * bg_amount: Amount of BG, EMD, or bill to be released. If the email is a tender security / EMD release notice, cross-reference the Project Dossier and state the tender security amount (e.g. "BDT ৭০,০০০/- (জমা দেওয়া পে-অর্ডার)"). If a bill follow-up without stated amount, calculate from Project Dossier.
       * release_status: Current processing status (e.g. "মূল পে-অর্ডার প্রত্যাহারের জন্য প্রস্তুত" or "বিল ছাড়করণ প্রক্রিয়াধীন").
       * bank_action: Required banking step or office collection step.

4. FORMULATE THE CRITICAL ACTION ITEM (Strictly in professional Bengali, using "আপনি" tone, zero familiar slang. Keep it SHORT, CRISP, and ACTIONABLE — MAXIMUM 2 CONCISE BULLETS, 1-2 lines each. DO NOT write long explanatory essays):
   - For 1_NEW_RFQ:
       * If this is a BUDGETARY OFFER / ESTIMATION ENQUIRY: State clearly that NO tender security or pay order is needed (এটি প্রাথমিক বাজেটারি কোটেশন বিধায় কোনো পে-অর্ডার বা জামানতের প্রয়োজন নেই). Instruct staff to prepare the itemized quotation on company letterhead and email it before deadline.
       * If this is a CREDENTIAL SUBMISSION / SHORTLISTING / QUALIFICATION REQUIREMENT (LTM):
          ১. আর্থিক যোগ্যতা: ইমেইলে উল্লেখিত বিগত ৩ বছরের সমজাতীয় কাজের ন্যূনতম কার্যাদেশের টাকার অংক ও ব্যাংক সলভেন্সির পরিমাণ স্পষ্ট উল্লেখ করুন (যেমন: বিগত ৩ বছরে ন্যূনতম BDT [অংক] টাকার একক/যৌথ কার্যাদেশ এবং BDT [অংক] টাকার ব্যাংক সলভেন্সি আবশ্যক)।
          ২. দাখিল ও চেকলিস্ট: হালনাগাদ ট্রেড লাইসেন্স, টিআইএন, ভ্যাট/বিআইএন, এনআইডি ও অভিজ্ঞতার সনদসমূহ কোম্পানির লেটারহেডে সিল-স্বাক্ষরসহ [জমার ডেডলাইন]-এর মধ্যে দাখিল নিশ্চিত করুন।
       * If this is a REVISED TENDER DOCUMENT / CORRIGENDUM / AMENDMENT (or the email mentions "Edited Tender Documents", "Revised NIT", "Rev01", "Corrigendum", "Addendum"):
          ১. সংশোধিত বিজ্ঞপ্তি সতর্কতা: এটি সংশোধিত দরপত্র নথি (Revised Tender Document); দরপত্র প্রস্তুতের ক্ষেত্রে পূর্বের ড্রাফট/ফাইল বাতিল করে এই নতুন সংযুক্তি ও স্পেক্স অনুসরণ নিশ্চিত করুন।
          ২. জামানত ও দাখিল: [সংশোধিত বা বহাল থাকা জামানত ও চূড়ান্ত ডেডলাইনের মধ্যে ড্রপ বক্সে দাখিল]।
       * If this is a FORMAL TENDER RFQ: Give only the 2 most vital instructions:
          ১. জামানত: [সুনির্দিষ্ট টাকার অংক ও প্রাপক প্রতিষ্ঠানের সঠিক নাম]।
          ২. দাখিল: [টেন্ডার বক্সে ড্রপ করার স্থান ও চূড়ান্ত সময়সীমা]।
   - For 2_NEGOTIATION:
       (a) If this is a TENDER AMENDMENT / CORRIGENDUM:
          ১. সংশোধিত শর্ত পর্যালোচনা: বর্ধিত ডেলিভারি শিডিউল (৪৫ দিন) ও শিথিলকৃত স্পেক্স (Accord/Alliance শর্ত প্রত্যাহার) অন্তর্ভুক্ত করে প্রস্তাব প্রস্তুত/হালনাগাদ করুন।
          ২. দাখিল: অন্যান্য সব শর্ত ও টেকনিক্যাল স্পেক্স অপরিবর্তিত রেখে নির্ধারিত ডেডলাইনের মধ্যে সংশোধিত দরপত্র দাখিল নিশ্চিত করুন।
       (b) If the buyer requests justification or documentation, format the required papers as a numbered 1 & 2 checklist: (১) [Document 1, e.g. Reference POs/Invoices from other plants], (২) [Document 2, e.g. Manufacturer official price list and cost breakdown] so office staff can immediately pull the required records.
       (c) State whether an official reply on company letterhead (signed, sealed, and scanned as PDF) is required instead of a plain text email.
       (d) If the buyer challenges the price citing an earlier 'budgetary offer', remind the executive that under Bangladesh Public Procurement Rules (PPR-2008), budgetary offers are non-binding estimates; advise defending via verifiable raw material, shipping, and USD exchange rate escalation.
       (e) FIRM COMMERCIAL STANCE FOR MARGIN DEFENSE: If the conversation history shows that Enterprise Solutions has ALREADY provided a price discount in an earlier turn (e.g. Turn 2 or previous emails), explicitly provide this executive directive in critical_action:
       '💡 এক্সিকিউটিভ সিদ্ধান্ত: যেহেতু ইতিপূর্বে দরপত্র মূল্যায়নের স্বার্থে একটি ছাড় (Discount) প্রদান করা হয়েছে, তাই নতুন করে পুনরায় মূল্য হ্রাস করা অনুচিত হবে (এতে প্রজেক্টের নিট মার্জিন ক্ষতিগ্রস্ত হবে এবং বাণিজ্যিক দুর্বলতা প্রকাশ পাবে)। বরং ডলার সংকট, বিনিময় হার বৃদ্ধি (USD/BDT escalation) এবং কাস্টমস শুল্ক বৃদ্ধির বাস্তব উপাত্ত উপস্থাপন করে বিদ্যমান দরেই দৃঢ় অবস্থান (Firm Stand) বজায় রাখুন।'
   - For 3_PO_AWARD: For industrial OEM machinery/spares, alert management to immediately obtain the official 'Manufacturer Warranty & Material Test Certificate' from the principal/maker, as power plant store/accounts mandate this for bill approval.
   - For 4_DELIVERY_CHALLAN: Verify challan, gate pass, and EIC receiving.
   - For 5_PG_PAYMENT:
       * If this is a TENDER SECURITY / EMD / PAY ORDER RELEASE:
          ১. কর্তৃত্বপত্র ও সংগ্রহ: কোম্পানির লেটারহেডে প্রতিনিধির কর্তৃত্বপত্র (Authorization Letter) ও এনআইডিসহ সংশ্লিষ্ট অফিসে (যেমন: ঢাকা অফিস) পাঠিয়ে মূল পে-অর্ডার/ব্যাংক ড্রাফট সংগ্রহ করুন।
          ২. ব্যাংকে জমা: সংগৃহীত মূল পে-অর্ডারটি অবিলম্বে সংশ্লিষ্ট ব্যাংকে জমা দিয়ে অ্যাকাউন্টে ফান্ড রি-ক্রেডিট নিশ্চিত করুন।
       * If this is a BILL PAYMENT / PG RELEASE:
          ১. হিসাব বিভাগ যোগাযোগ: বিল ছাড়করণের জন্য পাওয়ার প্ল্যান্ট হিসাব বিভাগের সাথে যোগাযোগ করুন এবং বিল ভাউচার অনুসরণ করুন।
          ২. ব্যাংকিং ফলো-আপ: ব্যাংক গ্যারান্টি অবমুক্তির চিঠি ব্যাংকে প্রেরণ করে লিয়েন প্রত্যাহার নিশ্চিত করুন।

Respond ONLY with a valid JSON object in this exact schema:
{{
  "lifecycle_stage": "1_NEW_RFQ | 2_NEGOTIATION | 3_PO_AWARD | 4_DELIVERY_CHALLAN | 5_PG_PAYMENT",
  "plant_name": "Accurate plant name (e.g. প্ল্যান্ট-এ পাওয়ার প্ল্যান্ট (powergen_a) or প্ল্যান্ট-বি পাওয়ার প্ল্যান্ট (powergen_b))",
  "buyer_contact_person": "Full name, designation, mobile, email of the sender",
  "critical_action": "Specific next action in formal Bengali",
  
  "rfq_details": {{
    "tender_no": "...",
    "items_specs": "...",
    "submission_deadline": "...",
    "tender_security_emd": "...",
    "delivery_period": "...",
    "issuing_officer": "...",
    "prebid_meeting_date": "..."
  }},
  "negotiation_details": {{
    "tender_no": "...",
    "buyer_objection": "...",
    "discount_demand": "...",
    "deadline_pressure": "...",
    "recommended_counter": "..."
  }},
  "po_details": {{
    "po_number": "...",
    "total_contract_value": "...",
    "items_ordered": "...",
    "payment_lc_terms": "...",
    "warranty_period": "...",
    "delivery_deadline": "...",
    "tax_vat_details": "...",
    "performance_guarantee_pct": "..."
  }},
  "delivery_details": {{
    "challan_number": "...",
    "po_reference": "...",
    "dispatched_items": "...",
    "delivery_site": "...",
    "inspection_status": "..."
  }},
  "pg_details": {{
    "project_tender_id": "...",
    "bg_number": "...",
    "bg_amount": "...",
    "release_status": "...",
    "bank_action": "..."
  }}
}}
"""
        contents = [prompt]

        # Attach documents if available
        for doc in unpacked_items:
            if doc.get("file_type") == "pdf" and doc.get("content_type") == "bytes":
                contents.append({
                    "inline_data": {
                        "mime_type": "application/pdf",
                        "data": doc.get("data")
                    }
                })
            elif doc.get("file_type") in ("jpg", "jpeg", "png", "gif", "bmp", "webp") and doc.get("content_type") == "bytes":
                mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                            "gif": "image/gif", "bmp": "image/bmp", "webp": "image/webp"}
                contents.append({
                    "inline_data": {
                        "mime_type": mime_map.get(doc.get("file_type"), "image/jpeg"),
                        "data": doc.get("data")
                    }
                })
            elif doc.get("content_type") == "text":
                contents.append(f"\n[Document: {doc.get('source_file')}]\n{doc.get('data')}")

        # Robust model fallback list
        models_to_try = ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.1-flash-lite"]
        res = None
        last_err = None

        for m_name in models_to_try:
            try:
                res = self.gemini_client.models.generate_content(
                    model=m_name,
                    contents=contents
                )
                if res and res.text:
                    break
            except Exception as e:
                last_err = e
                time.sleep(1)

        if not res or not res.text:
            default_data["critical_action"] += f" (Auto-fallback: {last_err})"
            return default_data

        try:
            raw_text = res.text.strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            parsed = json.loads(raw_text)

            # Flatten stage-specific variables to root dictionary for direct template consumption
            stage = parsed.get("lifecycle_stage", "1_NEW_RFQ")
            flattened = {
                "lifecycle_stage": stage,
                "plant_name": parsed.get("plant_name", plant_guess),
                "buyer_contact_person": parsed.get("buyer_contact_person", ""),
                "critical_action": parsed.get("critical_action", "পরবর্তী পদক্ষেপ গ্রহণ করুন।"),
                "message_id": email_obj.get("id", "")
            }

            if stage == "1_NEW_RFQ" and "rfq_details" in parsed:
                flattened.update(parsed["rfq_details"])
            elif stage == "2_NEGOTIATION" and "negotiation_details" in parsed:
                flattened.update(parsed["negotiation_details"])
            elif stage == "3_PO_AWARD" and "po_details" in parsed:
                flattened.update(parsed["po_details"])
            elif stage == "4_DELIVERY_CHALLAN" and "delivery_details" in parsed:
                flattened.update(parsed["delivery_details"])
            elif stage == "5_PG_PAYMENT" and "pg_details" in parsed:
                flattened.update(parsed["pg_details"])

            return flattened

        except Exception as e:
            default_data["critical_action"] += f" (Auto-fallback: {e})"
            return default_data

    def _run_supplier_extraction(self, email_obj: Dict[str, Any], unpacked_items: List[Dict[str, Any]], project_summary: dict = None, active_history: list = None) -> Dict[str, Any]:
        """Tier 2: Supplier/OEM Quotation Extraction Engine."""
        headers = email_obj.get('headers', {})
        sender = headers.get('from', '')
        subj = headers.get('subject', '')
        body_snippet = email_obj.get('body', '')

        default_data = {
            "lifecycle_stage": "S1_QUOTE_RECEIVED",
            "plant_name": sender.split('@')[-1].split('>')[0] if '@' in sender else sender,
            "supplier_name": sender,
            "critical_action": "সাপ্লায়ার কোটেশন পর্যালোচনা করে প্রতিযোগী দরের সাথে তুলনা করুন।",
            "message_id": email_obj.get("id", "")
        }

        if not self.gemini_client:
            return default_data

        # Dossier context for cross-referencing tender
        dossier_ctx = ""
        if project_summary:
            if project_summary.get("title"):
                dossier_ctx += f"\n[PROJECT CONTEXT] Title: {project_summary.get('title')}"
            if project_summary.get("tender_no"):
                dossier_ctx += f"\n[PROJECT CONTEXT] Related Tender No: {project_summary.get('tender_no')}"

        # Cross-thread history — previous emails in same project
        history_ctx = ""
        if active_history:
            history_ctx = "\n[PREVIOUS EMAILS IN THIS PROJECT]\n"
            for i, h in enumerate(active_history[-5:], 1):
                h_summary = h.get("summary_text", "")[:150]
                h_stage = h.get("stage", "")
                h_sender = h.get("sender", "")[:40]
                history_ctx += f"  {i}. [{h_stage}] {h_sender}: {h_summary}\n"

        prompt = f"""
You are the Procurement Intelligence AI for Enterprise Trading Corporation (Buyer/Importer).
Analyze this SUPPLIER / OEM email and extract quotation details.

Email Subject: {subj}
Email Sender: {sender}
Email Body:
{body_snippet}
{dossier_ctx}
{history_ctx}

MANDATORY LANGUAGE RULE: All extracted values MUST be in professional formal Bengali (বাংলা).
English permitted ONLY for part numbers, model names, brand names, currency symbols (BDT, USD, EUR).

TASK:
1. IDENTIFY SUPPLIER LIFECYCLE STAGE (exactly one):
   - "S1_QUOTE_RECEIVED": Supplier sent a price quotation / proforma invoice
   - "S2_UNDER_REVIEW": Follow-up or revision of existing quotation
   - "S3_ORDER_PLACED": Confirmation that order has been placed with supplier
   - "S4_AWAITING_DELIVERY": Tracking shipment or delivery from supplier

2. EXTRACT THESE VARIABLES:
   - supplier_name: Full company name of the supplier/OEM
   - quoted_items: Itemized list with part numbers, quantities, and descriptions
   - unit_prices: Per-item prices with currency
   - total_quoted_amount: Total quotation value with currency
   - delivery_lead_time: Promised delivery timeline
   - quote_validity: How long the quote is valid
   - payment_terms: Payment conditions (advance %, LC, T/T, etc.)
   - supplier_country: Country of origin/manufacturing (e.g. ভারত, চীন, সিঙ্গাপুর)
   - incoterms: Delivery terms (FOB / CIF / EXW / CFR / DDP etc.)
   - currency: Quotation currency (INR / USD / EUR / BDT)
   - proforma_invoice_no: Proforma Invoice number if applicable, otherwise 'প্রযোজ্য নয়'
   - related_tender_ref: Which buyer tender/RFQ this quote responds to (if identifiable)
   - critical_action: What Enterprise Trading Corporation should do next (in formal Bengali, max 2 bullets)

Respond ONLY with valid JSON:
{{
  "lifecycle_stage": "S1_QUOTE_RECEIVED | S2_UNDER_REVIEW | S3_ORDER_PLACED | S4_AWAITING_DELIVERY",
  "supplier_name": "...",
  "quoted_items": "...",
  "unit_prices": "...",
  "total_quoted_amount": "...",
  "delivery_lead_time": "...",
  "quote_validity": "...",
  "payment_terms": "...",
  "supplier_country": "...",
  "incoterms": "...",
  "currency": "...",
  "proforma_invoice_no": "...",
  "related_tender_ref": "...",
  "critical_action": "..."
}}
"""
        return self._call_gemini_and_parse(prompt, unpacked_items, default_data, email_obj)

    def _run_bank_extraction(self, email_obj: Dict[str, Any], unpacked_items: List[Dict[str, Any]], project_summary: dict = None, active_history: list = None) -> Dict[str, Any]:
        """Tier 3: Bank/Trade Finance Extraction Engine."""
        headers = email_obj.get('headers', {})
        sender = headers.get('from', '')
        subj = headers.get('subject', '')
        body_snippet = email_obj.get('body', '')

        default_data = {
            "lifecycle_stage": "B1_LC_DRAFT",
            "plant_name": sender.split('@')[-1].split('>')[0] if '@' in sender else sender,
            "bank_name": sender,
            "critical_action": "ব্যাংকিং ডকুমেন্ট পর্যালোচনা করে প্রয়োজনীয় পদক্ষেপ গ্রহণ করুন।",
            "message_id": email_obj.get("id", "")
        }

        if not self.gemini_client:
            return default_data

        dossier_ctx = ""
        if project_summary:
            if project_summary.get("title"):
                dossier_ctx += f"\n[PROJECT CONTEXT] Title: {project_summary.get('title')}"
            if project_summary.get("tender_no"):
                dossier_ctx += f"\n[PROJECT CONTEXT] Related Tender No: {project_summary.get('tender_no')}"

        # Cross-thread history — previous banking emails in same project
        history_ctx = ""
        if active_history:
            history_ctx = "\n[PREVIOUS EMAILS IN THIS PROJECT]\n"
            for i, h in enumerate(active_history[-5:], 1):
                h_summary = h.get("summary_text", "")[:150]
                h_stage = h.get("stage", "")
                h_sender = h.get("sender", "")[:40]
                history_ctx += f"  {i}. [{h_stage}] {h_sender}: {h_summary}\n"

        prompt = f"""
You are the Trade Finance AI for Enterprise Trading Corporation.
Analyze this BANK / FINANCIAL email and extract LC/payment details.

Email Subject: {subj}
Email Sender: {sender}
Email Body:
{body_snippet}
{dossier_ctx}
{history_ctx}

MANDATORY LANGUAGE RULE: All extracted values MUST be in professional formal Bengali (বাংলা).
English permitted ONLY for LC numbers, SWIFT codes, reference numbers, currency symbols.

TASK:
1. IDENTIFY BANKING LIFECYCLE STAGE (exactly one):
   - "B1_LC_DRAFT": LC draft received or under amendment review
   - "B2_LC_OPENED": LC formally opened / confirmed
   - "B3_DOCS_SUBMITTED": Bill of Entry / SWIFT / shipping docs submitted to bank
   - "B4_PAYMENT_RECEIVED": Payment credited / fund transfer completed

2. EXTRACT THESE VARIABLES:
   - bank_name: Full name of the bank/financial institution
   - document_type: Type of document (LC Draft / LC Amendment / SWIFT / Bill of Entry / Fund Transfer / Pay Order)
   - lc_number: LC number or reference number
   - amount: Amount with currency (BDT/USD)
   - beneficiary: Who receives the payment
   - applicant: Who opens/pays the LC
   - opening_date: When LC was opened or document dated
   - expiry_date: LC expiry or document validity deadline
   - shipment_date: Latest shipment date (if applicable)
   - lc_type: LC type (Sight / Deferred / UPAS / Back-to-Back / At Sight). If TT/Fund Transfer, write 'প্রযোজ্য নয় (টেলিগ্রাফিক ট্রান্সফার)'
   - documents_required: List of required shipping/banking documents mentioned in LC (e.g. Commercial Invoice, Bill of Lading, Certificate of Origin, Insurance, Packing List). If not stated, write 'বিজ্ঞপ্তিতে সুনির্দিষ্ট নয়'
   - tt_reference_no: SWIFT TT reference number for fund transfers. If LC, write 'প্রযোজ্য নয়'
   - related_tender_ref: Which procurement/PO this LC relates to
   - critical_action: What Enterprise Trading Corporation should do next (in formal Bengali, max 2 bullets)

Respond ONLY with valid JSON:
{{
  "lifecycle_stage": "B1_LC_DRAFT | B2_LC_OPENED | B3_DOCS_SUBMITTED | B4_PAYMENT_RECEIVED",
  "bank_name": "...",
  "document_type": "...",
  "lc_number": "...",
  "amount": "...",
  "beneficiary": "...",
  "applicant": "...",
  "opening_date": "...",
  "expiry_date": "...",
  "shipment_date": "...",
  "lc_type": "...",
  "documents_required": "...",
  "tt_reference_no": "...",
  "related_tender_ref": "...",
  "critical_action": "..."
}}
"""
        return self._call_gemini_and_parse(prompt, unpacked_items, default_data, email_obj)

    def _call_gemini_and_parse(self, prompt: str, unpacked_items: List[Dict[str, Any]], default_data: dict, email_obj: dict) -> dict:
        """Shared Gemini API call + JSON parse logic for all tiers."""
        contents = [prompt]
        for doc in unpacked_items:
            if doc.get("file_type") == "pdf" and doc.get("content_type") == "bytes":
                contents.append({
                    "inline_data": {
                        "mime_type": "application/pdf",
                        "data": doc.get("data")
                    }
                })
            elif doc.get("file_type") in ("jpg", "jpeg", "png", "gif", "bmp", "webp") and doc.get("content_type") == "bytes":
                mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                            "gif": "image/gif", "bmp": "image/bmp", "webp": "image/webp"}
                contents.append({
                    "inline_data": {
                        "mime_type": mime_map.get(doc.get("file_type"), "image/jpeg"),
                        "data": doc.get("data")
                    }
                })
            elif doc.get("content_type") == "text":
                contents.append(f"\n[Document: {doc.get('source_file')}]\n{doc.get('data')}")

        models_to_try = ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.1-flash-lite"]
        res = None
        last_err = None

        for m_name in models_to_try:
            try:
                res = self.gemini_client.models.generate_content(
                    model=m_name,
                    contents=contents
                )
                if res and res.text:
                    break
            except Exception as e:
                last_err = e
                time.sleep(1)

        if not res or not res.text:
            default_data["critical_action"] += f" (Auto-fallback: {last_err})"
            return default_data

        try:
            raw_text = res.text.strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            parsed = json.loads(raw_text)

            # Merge parsed into default_data (parsed values override defaults)
            result = {**default_data, **parsed}
            result["message_id"] = email_obj.get("id", "")
            return result

        except Exception as e:
            default_data["critical_action"] += f" (Auto-fallback: {e})"
            return default_data
