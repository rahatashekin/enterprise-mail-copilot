"""
Core Tender Parser, Context Assembler & Executive Multi-Archetype WhatsApp Formatter
Enterprise Trading Corporation

Implements:
  - Context Reconstruction (Multi-turn dialogue memory)
  - 5 Dedicated Corporate Executive WhatsApp Templates matching SS1:
    1. NEW_TENDER_RFQ (🔔 নতুন দরপত্র নোটিশ)
    2. TENDER_NEGOTIATION (🤝 দর কষাকষি ও প্রাইস জাস্টিফিকেশন)
    3. PURCHASE_ORDER_AWARD (🎉 নতুন কার্যাদেশ / Purchase Order প্রাপ্তি)
    4. GOODS_DELIVERY_CHALLAN (🚚 পণ্য সরবরাহ ও চালান ট্র্যাকিং)
    5. PG_PAYMENT_RELEASE (💰 জামানত / PG অবমুক্তি ও বিল ট্র্যাকিং)

Rules:
  - Strictly formal, neutral corporate executive tone ("আপনি" based, zero familiar slang).
  - No empty or dummy N/A fields.
  - Action-oriented next steps.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

class ContextAssembler:
    """Reconstructs historical dialogue context across multi-turn email threads."""

    def __init__(self, emails_json_path: Path):
        self.emails_path = emails_json_path
        self._threads_cache = None

    def _load_threads(self):
        if self._threads_cache is None:
            with open(self.emails_path, 'r', encoding='utf-8') as f:
                emails = json.load(f)
            threads = {}
            for e in emails:
                tid = e.get('thread_id')
                if tid:
                    threads.setdefault(tid, []).append(e)
            for tid in threads:
                threads[tid].sort(key=lambda x: int(x.get('internal_date', 0)))
            self._threads_cache = threads

    def assemble_context(self, current_message_id: str) -> Dict[str, Any]:
        self._load_threads()
        target_thread = None
        target_msg = None
        turn_idx = -1

        for tid, msgs in self._threads_cache.items():
            for idx, m in enumerate(msgs):
                if m.get('id') == current_message_id:
                    target_thread = msgs
                    target_msg = m
                    turn_idx = idx
                    break
            if target_msg:
                break

        if not target_msg:
            return {"error": "Message not found", "turn_number": 1}

        context = {
            "current_message_id": current_message_id,
            "thread_id": target_msg.get("thread_id"),
            "turn_number": turn_idx + 1,
            "total_turns_so_far": len(target_thread),
            "subject": target_msg.get("headers", {}).get("subject", ""),
            "current_sender": target_msg.get("headers", {}).get("from", ""),
            "current_date": target_msg.get("headers", {}).get("date", ""),
            "current_body": target_msg.get("body", "")[:2500],
            "is_outgoing": "enterprise.automation@example.com" in target_msg.get("headers", {}).get("from", "").lower(),
            "dialogue_history": []
        }

        # Build complete chronological dialogue transcript of both parties
        for i, m in enumerate(target_thread[:turn_idx]):
            sender = m.get("headers", {}).get("from", "")
            is_dig = "enterprise.automation@example.com" in sender.lower() or "lead" in sender.lower()
            context["dialogue_history"].append({
                "turn": i + 1,
                "party": "Enterprise Solutions" if is_dig else "Buyer / Plant",
                "sender": sender,
                "date": m.get("headers", {}).get("date", ""),
                "snippet": m.get("body", "")[:400]
            })

        return context


import re

def clean_dossier_title(raw_title: str) -> str:
    """Cleans raw email subjects into concise, professional dossier titles generically."""
    if not raw_title:
        return "Industrial Procurement Package"
    
    # 1. Strip Re:, Fwd:, FW:
    t = re.sub(r'^(?:(?:Re|Fwd|FW):\s*)+', '', str(raw_title), flags=re.IGNORECASE).strip()
    
    # 2. Administrative communication prefixes
    prefixes = [
        r'Regarding\s+issuance\s+of\s+Tender\s+Documents?\s+(?:for\s+)?',
        r'Regarding\s+issuance\s+of\s+(?:NOA|PO)\s+(?:for\s+)?',
        r'Regarding\s+issuance\s+of\s+',
        r'ISSUANCE\s+OF\s+(?:TENDER\s+DOCUMENTS?\s+FOR\s+)?',
        r'Regarding\s+price\s+justifications?\s+(?:for\s+)?',
        r'Regarding\s+(?:shortfall\s+)?(?:documents?\s+)?(?:for\s+)?',
        r'(?:Regarding\s+)?(?:Submission\s+of\s+)?Credentials?\s*(?:Submissions?)?\s*(?:for\s+(?:vendor\s+)?shortlisting\s*)?(?:for\s+)?',
        r'Release\s+of\s+tender\s+security\s+(?:for\s+)?',
        r'Budgetary\s+offers?\s+(?:for\s+)?',
        r'Regarding\s+',
        r'Price\s+Justifications?\s+(?:for\s+)?',
        r'Notification\s+of\s+Award\s*(?:\(NOA\))?\s+(?:for\s+)?',
        r'NOA\s+for\s+',
        r'Purchase\s+Orders?\s+(?:for\s+)?',
        r'PO\s+for\s+',
        r'Request\s+for\s+(?:budgetary\s+)?quotations?\s+(?:for\s+)?',
        r'Request\s+for\s+the\s+Bill\s+payment\s+against\s+[^\n]+',
        r'Tender\s+Documents?\s+(?:for\s+)?',
        r'PROCUREMENT\s+OF\s+',
        r'SUPPLY\s+OF\s+',
        r'the\s+',
    ]
    
    # Iteratively strip quotes, dashes, and administrative prefixes
    changed = True
    while changed:
        orig = t
        t = t.strip('“"\'`”‘’ \t\r\n-–—:')
        for p in prefixes:
            t = re.sub(f'^{p}', '', t, flags=re.IGNORECASE).strip()
            t = re.sub(f'\\b{p}', '', t, flags=re.IGNORECASE).strip()
        t = t.strip('“"\'`”‘’ \t\r\n-–—:')
        changed = (t != orig)

    # 3. Clean plant/capacity location suffixes
    t = re.sub(r'\s+at\s+\d+\s*[xX×]\s*\d+\s*MW[^\n]*', '', t, flags=re.IGNORECASE).strip()
    t = re.sub(r',\s*(?:powergen_a|powergen_b|BPDB|APSCL|NWPGCL|EGCB|RPCL)[^\n]*', '', t, flags=re.IGNORECASE).strip()
    t = t.strip('“"\'`”‘’ .:-–—')

    if not t:
        return "Industrial Procurement Package"
    
    # Capitalize title words cleanly if all uppercase
    if t.isupper():
        t = t.title()

    # Concise length bound without cutting in the middle of a word
    if len(t) > 50:
        words = t[:50].rsplit(' ', 1)[0]
        return words.strip(' ,.-')
    return t


def _normalize_bengali_time(text: str) -> str:
    """Converts mixed 24-hour periods (e.g. 'দুপুর ১৪:৩০', 'বিকাল ১৭:০০') into natural 12-hour phrasing ('দুপুর ২:৩০', 'বিকাল ৫:০০')."""
    if not text:
        return text
    bn_to_en = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')
    en_to_bn = str.maketrans('0123456789', '০১২৩৪৫৬৭৮৯')
    def repl(m):
        period = m.group(1)
        raw_hr = m.group(2).translate(bn_to_en)
        raw_min = m.group(3).translate(bn_to_en)
        hr_int = int(raw_hr)
        if 13 <= hr_int <= 23:
            hr_12 = hr_int - 12
            return f"{period} {str(hr_12).translate(en_to_bn)}:{raw_min.translate(en_to_bn)}"
        elif hr_int == 12:
            return f"{period} ১২:{raw_min.translate(en_to_bn)}"
        return m.group(0)
    pattern = r'(দুপুর|বেলা|বিকাল|সন্ধ্যা|রাত)\s*([1-2][0-9]|[১-২][০-৯]):([0-5][0-9]|[০-৫][০-৯])'
    return re.sub(pattern, repl, str(text))


def _clean_bengali_desc(val: Any, default_bn: str = "বিজ্ঞপ্তিতে সুনির্দিষ্ট নয়") -> str:
    """Translates/normalizes common English placeholder phrases into clean corporate Bengali."""
    if not val:
        return default_bn
    s = str(val).strip()
    s_lower = s.lower()
    if s_lower in ["not specified", "not mentioned", "n/a", "none", "not defined", "null"]:
        return default_bn
    if "not applicable" in s_lower or s_lower == "n/a":
        if "budgetary" in s_lower:
            return "প্রযোজ্য নয় (বাজেটারি অফার)"
        return "শর্ত প্রযোজ্য নয়"
    if "immediate action recommended" in s_lower or "as soon as possible" in s_lower or "asap" in s_lower:
        if "not specified" in s_lower:
            return "বিজ্ঞপ্তিতে সুনির্দিষ্ট নয় (জরুরি ভিত্তিতে প্রেরণ বাঞ্ছনীয়)"
        return "জরুরি ভিত্তিতে প্রেরণ বাঞ্ছনীয়"
    return _normalize_bengali_time(s)


def _format_item_list(items_str: Any) -> str:
    """Formats multi-item schedules into clean indented mobile bullet points."""
    if not items_str:
        return "তালিকা সংযুক্ত নথিতে রয়েছে"
    s = str(items_str).strip()
    # Split by semicolon OR comma preceding a numbered item (e.g. ", ২." or ", 2.")
    parts = [p.strip() for p in re.split(r';\s*|,\s*(?=[1-9১-৯\d]+\.)', s) if p.strip()]
    if len(parts) > 1:
        return "\n  • " + "\n  • ".join(parts)
    if s.startswith(('১.', '1.', '•')):
        return f"\n  • {s}"
    return s


def _format_critical_action(action_str: Any) -> str:
    """Ensures critical action points are clean, concise, and each numbered point is on a new line."""
    if not action_str:
        return "মেইলটি পর্যালোচনা করে পরবর্তী পদক্ষেপ গ্রহণ করুন।"
    s = str(action_str).strip()
    s = _normalize_bengali_time(s)
    # If multiple numbered points are inline (e.g. "। ২." or ". 2."), split them cleanly onto new lines
    s = re.sub(r'([।!?.\n])\s*([২-৯2-9]\.)', r'\1\n\2', s)
    return s


class WhatsAppFormatter:
    """Generates corporate executive WhatsApp alerts across the 5 lifecycle stages."""

    @classmethod
    def format_alert(cls, stage: str, data: Dict[str, Any], context: Dict[str, Any]) -> str:
        msg_id = data.get("message_id") or context.get("current_message_id", "")
        gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{msg_id}"
        sheet_link = context.get("sheet_url", "")

        source = data.get("plant_name") or data.get("supplier_name") or data.get("bank_name") or "অজ্ঞাত উৎস"
        raw_action = data.get("critical_action", "মেইলটি পর্যালোচনা করে পরবর্তী পদক্ষেপ গ্রহণ করুন।")
        critical_action = _format_critical_action(raw_action)

        # Parse email date for display
        raw_date = context.get("email_date", "")
        date_line = ""
        if raw_date:
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(raw_date)
                # Bengali month names
                bn_months = {1: "জানুয়ারি", 2: "ফেব্রুয়ারি", 3: "মার্চ", 4: "এপ্রিল",
                             5: "মে", 6: "জুন", 7: "জুলাই", 8: "আগস্ট",
                             9: "সেপ্টেম্বর", 10: "অক্টোবর", 11: "নভেম্বর", 12: "ডিসেম্বর"}
                # Bengali digits
                en_to_bn = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
                day = str(dt.day).translate(en_to_bn)
                year = str(dt.year).translate(en_to_bn)
                month = bn_months.get(dt.month, str(dt.month))
                date_line = f"📅 {day} {month} {year}\n"
            except Exception:
                date_line = f"📅 {raw_date[:25]}\n"

        # ============ TIER 2: SUPPLIER TEMPLATES ============
        if stage in ["S1_QUOTE_RECEIVED", "S2_UNDER_REVIEW", "S3_ORDER_PLACED", "S4_AWAITING_DELIVERY"]:
            return cls._format_supplier_alert(stage, data, source, critical_action, gmail_link, sheet_link, date_line)

        # ============ TIER 3: BANK TEMPLATES ============
        if stage in ["B1_LC_DRAFT", "B2_LC_OPENED", "B3_DOCS_SUBMITTED", "B4_PAYMENT_RECEIVED"]:
            return cls._format_bank_alert(stage, data, source, critical_action, gmail_link, sheet_link, date_line)

        # -------------------------------------------------------------
        # 1. NEW TENDER RFQ (🔔 নতুন দরপত্র নোটিশ)
        # -------------------------------------------------------------
        if stage in ["1_NEW_RFQ", "NEW_TENDER_RFQ"]:
            raw_tender_no = data.get("tender_no", "বিজ্ঞপ্তিতে সুনির্দিষ্ট নয়")
            s_t = str(raw_tender_no).strip()
            if s_t.lower() in ["n/a", "none", "null", ""]:
                tender_no = "বিজ্ঞপ্তিতে সুনির্দিষ্ট নয়"
            elif s_t.lower() == "n/a (budgetary enquiry)":
                tender_no = "প্রযোজ্য নয় (বাজেটারি অনুসন্ধান)"
            else:
                tender_no = s_t

            raw_items = data.get("items_specs", data.get("items_summary", "তালিকা সংযুক্ত ফাইলেই রয়েছে"))
            items = _format_item_list(raw_items)
            deadline = _clean_bengali_desc(data.get("submission_deadline"), "বিজ্ঞপ্তিতে সুনির্দিষ্ট নয়")
            officer = data.get("issuing_officer", data.get("officer_name", "ক্রয় বিভাগ"))
            emd = _clean_bengali_desc(data.get("tender_security_emd"), "শর্ত প্রযোজ্য নয়")
            delivery = _clean_bengali_desc(data.get("delivery_period"), "বিজ্ঞপ্তিতে সুনির্দিষ্ট নয়")

            msg = (
                f"🔔 *নতুন দরপত্র নোটিশ* ({source})\n"
                f"{date_line}"
                f"──────────────────────────────\n"
                f"📋 *টেন্ডার বিবরণ:*\n"
                f"• টেন্ডার নং: `{tender_no}`\n"
                f"• আইটেম ও স্পেক্স: {items}\n"
                f"• জমা দেওয়ার শেষ সময়: *{deadline}*\n"
                f"• টেন্ডার সিকিউরিটি (EMD): {emd}\n"
                f"• ডেলিভারির সময়সীমা: {delivery}\n"
                f"• সংশ্লিষ্ট কর্মকর্তা: {officer}\n"
            )
            if data.get('buyer_contact_person') and data.get('buyer_contact_person') != 'N/A':
                msg += f"• যোগাযোগ: {data['buyer_contact_person']}\n"
            if data.get('prebid_meeting_date') and data.get('prebid_meeting_date') != 'N/A':
                msg += f"• প্রি-বিড মিটিং: {data['prebid_meeting_date']}\n"
            msg += (
                f"──────────────────────────────\n"
                f"🎯 *জরুরি করণীয়:*\n{critical_action}\n"
                f"──────────────────────────────\n"
                f"📧 সরাসরি জিমেইলে দেখুন: {gmail_link}\n"
                f"📊 লাইভ ট্র্যাকার শিট: {sheet_link}"
            )
            return msg

        # -------------------------------------------------------------
        # 2. NEGOTIATION & CORRIGENDUM (🤝 দর কষাকষি ও টেন্ডার সংশোধনী)
        # -------------------------------------------------------------
        elif stage in ["2_NEGOTIATION", "ONGOING_PRICE_NEGOTIATION", "TENDER_CORRIGENDUM_AMENDMENT"]:
            raw_tender_no = data.get("tender_no", "N/A")
            if not raw_tender_no or str(raw_tender_no).strip().upper() in ["N/A", "NONE", "NULL"]:
                raw_tender_no = context.get("tender_no") or context.get("project_id", "N/A")
            tender_no = str(raw_tender_no).strip()

            objection = data.get("buyer_objection", "অফিসিয়াল প্রাইস জাস্টিফিকেশন চাওয়া হয়েছে")
            discount = data.get("discount_demand", "স্পেসিফিকেশন অথবা রেট রিডাকশন পর্যালোচনা")
            raw_pressure = data.get("deadline_pressure", "জরুরি ভিত্তিতে উত্তর প্রযোজ্য")
            pressure = _normalize_bengali_time(raw_pressure)
            counter = data.get("recommended_counter", "কস্ট ব্রেকডাউন ও যুক্তি উপস্থাপন")

            # Check if this negotiation event is a Corrigendum / Tender Amendment
            subj_lower = str(context.get("subject", "")).lower()
            body_lower = str(context.get("current_body", "")).lower()
            is_amendment = (
                any(k in subj_lower for k in ["amendment", "corrigendum", "addendum", "সংশোধনী", "করিন্ডাম"]) or
                any(k in body_lower for k in ["tender amendment", "corrigendum no", "amendment no", "addendum no"])
            )

            if is_amendment:
                header_title = "📢 *দরপত্র সংশোধনী নোটিশ (Corrigendum / Amendment)*"
                label_objection = "সংশোধনীর বিষয়বস্তু:"
                label_discount = "পরিবর্তিত শর্তসমূহ:"
                label_pressure = "সংশোধিত/কার্যকর সময়সীমা:"
                label_counter = "প্রস্তাবিত প্রস্তুতি:"
                action_header = "🎯 *জরুরি করণীয়:*"
            else:
                header_title = "🤝 *দরপত্র দর কষাকষি / জাস্টিফিকেশন নোটিশ*"
                label_objection = "বায়ারের মূল বক্তব্য:"
                label_discount = "ডিসকাউন্ট / সংশোধনী দাবি:"
                label_pressure = "সময়সীমা ও চাপ:"
                label_counter = "প্রস্তাবিত অবস্থান:"
                action_header = "🎯 *ব্যবসায়িক করণীয়:*"

            msg = (
                f"{header_title}\n"
                f"🏛️ প্রতিষ্ঠান: *{source}*\n"
                f"{date_line}"
                f"──────────────────────────────\n"
                f"📋 *প্যাকেজ রেফারেন্স:* `{tender_no}`\n"
                f"• {label_objection} {objection}\n"
                f"• {label_discount} {discount}\n"
                f"• {label_pressure} *{pressure}*\n"
                f"• {label_counter} {counter}\n"
            )
            if data.get('buyer_contact_person') and data.get('buyer_contact_person') != 'N/A':
                msg += f"• যোগাযোগ: {data['buyer_contact_person']}\n"
            msg += (
                f"──────────────────────────────\n"
                f"{action_header}\n{critical_action}\n"
                f"──────────────────────────────\n"
                f"📧 সরাসরি থ্রেডে উত্তর দিন: {gmail_link}\n"
                f"📊 লাইভ ট্র্যাকার শিট: {sheet_link}"
            )
            return msg

        # -------------------------------------------------------------
        # 3. PURCHASE ORDER / AWARD (🎉 নতুন কার্যাদেশ প্রাপ্তি)
        # -------------------------------------------------------------
        elif stage in ["3_PO_AWARD", "AWARD_OR_PURCHASE_ORDER"]:
            po_no = data.get("po_number", data.get("tender_no", "N/A"))
            value = data.get("total_contract_value", "পিও ডকুমেন্টে উল্লেখিত")
            raw_items = data.get("items_ordered", data.get("items_summary", "অর্ডার তালিকা অনুযায়ী"))
            payment = _clean_bengali_desc(data.get("payment_lc_terms"), "চুক্তি অনুযায়ী")
            warranty = _clean_bengali_desc(data.get("warranty_period"), "১২/১৮ মাস")
            delivery = _clean_bengali_desc(data.get("delivery_deadline"), "চুক্তির শর্তানুযায়ী")

            # Adaptive check: NOA vs final Purchase Order (PO)
            combined_text = (str(context.get("subject", "")) + " " + 
                             str(context.get("current_body", "")) + " " + 
                             str(data.get("critical_action", ""))).lower()
            
            is_noa = (
                ("notification of award" in combined_text or "নোটিফিকেশন অব অ্যাওয়ার্ড" in combined_text or "noa" in combined_text)
                and not ("enclosed po" in combined_text or "attached po" in combined_text or "purchase order" in combined_text)
            )
            
            if is_noa:
                stage_badge = "🎉 *নোটিফিকেশন অব অ্যাওয়ার্ড (NOA) প্রাপ্তি*"
                ref_label = "অ্যাওয়ার্ড / NOA রেফারেন্স:"
                items_str = str(raw_items).strip()
                if items_str and not any(char.isdigit() for char in items_str[:4]) and "বিওকিউ" not in items_str and "স্পেসিফিকেশন" not in items_str:
                    items = f"{items_str} (অনুমোদিত দরপত্র বিওকিউ ও স্পেসিফিকেশন অনুযায়ী)"
                else:
                    items = _format_item_list(raw_items)
            else:
                stage_badge = "🎉 *নতুন কার্যাদেশ / Purchase Order প্রাপ্তি*"
                ref_label = "পারচেজ অর্ডার (PO) নং:"
                items = _format_item_list(raw_items)

            msg = (
                f"{stage_badge}\n"
                f"🏛️ প্রতিষ্ঠান: *{source}*\n"
                f"{date_line}"
                f"──────────────────────────────\n"
                f"📦 *কার্যাদেশ বিবরণ:*\n"
                f"• {ref_label} `{po_no}`\n"
                f"• মোট চুক্তিমূল্য: *{value}*\n"
                f"• অনুমোদিত মালামাল: {items}\n"
                f"• পেমেন্ট ও এলসি শর্ত: {payment}\n"
                f"• ওয়ারেন্টি পিরিয়ড: {warranty}\n"
                f"• ডেলিভারি ডেডলাইন: *{delivery}*\n"
            )
            if data.get('buyer_contact_person') and data.get('buyer_contact_person') != 'N/A':
                msg += f"• যোগাযোগ: {data['buyer_contact_person']}\n"
            if data.get('tax_vat_details') and data.get('tax_vat_details') != 'N/A':
                msg += f"• ট্যাক্স ও ভ্যাট: {data['tax_vat_details']}\n"
            if data.get('performance_guarantee_pct') and data.get('performance_guarantee_pct') != 'N/A':
                msg += f"• পারফরমেন্স গ্যারান্টি: {data['performance_guarantee_pct']}\n"
            msg += (
                f"──────────────────────────────\n"
                f"🎯 *অপারেশনাল করণীয়:*\n{critical_action}\n"
                f"──────────────────────────────\n"
                f"📧 অফিশিয়াল কার্যাদেশ দেখুন: {gmail_link}\n"
                f"📊 লাইভ ট্র্যাকার শিট: {sheet_link}"
            )
            return msg

        # -------------------------------------------------------------
        # 4. DELIVERY & CHALLAN (🚚 পণ্য সরবরাহ ও চালান ট্র্যাকিং)
        # -------------------------------------------------------------
        elif stage in ["4_DELIVERY_CHALLAN", "GOODS_DELIVERY_CHALLAN"]:
            challan_no = data.get("challan_number", "চালানপত্র সংযুক্ত")
            po_ref = data.get("po_reference", data.get("tender_no", "N/A"))
            raw_dispatched = data.get("dispatched_items", data.get("items_summary", "চালান অনুযায়ী মালামাল"))
            dispatched = _format_item_list(raw_dispatched)
            site = data.get("delivery_site", "প্ল্যান্ট ওয়্যারহাউস")
            inspection = data.get("inspection_status", "আনলোডিং ও কোয়ালিটি চেকের প্রস্তুতি")

            msg = (
                f"🚚 *পণ্য সরবরাহ ও চালান নোটিফিকেশন*\n"
                f"🏛️ গ্রাহক: *{source}*\n"
                f"{date_line}"
                f"──────────────────────────────\n"
                f"📦 *চালান ও সরবরাহ বিবরণ:*\n"
                f"• চালান নম্বর: `{challan_no}`\n"
                f"• পারচেজ অর্ডার (PO) নং: `{po_ref}`\n"
                f"• সরবরাহকৃত মালামাল: {dispatched}\n"
                f"• ডেলিভারি লোকেশন: *{site}*\n"
                f"• ইন্সপেকশন স্ট্যাটাস: {inspection}\n"
            )
            if data.get('buyer_contact_person') and data.get('buyer_contact_person') != 'N/A':
                msg += f"• যোগাযোগ: {data['buyer_contact_person']}\n"
            msg += (
                f"──────────────────────────────\n"
                f"🎯 *সাইট করণীয়:*\n{critical_action}\n"
                f"──────────────────────────────\n"
                f"📧 চালান কপি ও বিস্তারিত: {gmail_link}\n"
                f"📊 লাইভ ট্র্যাকার শিট: {sheet_link}"
            )
            return msg

        # -------------------------------------------------------------
        # 5. PG & PAYMENT RELEASE (💰 জামানত ও বিল ট্র্যাকিং)
        # -------------------------------------------------------------
        elif stage in ["5_PG_PAYMENT", "PG_RELEASE_PAYMENT_TRACKING"]:
            raw_proj_id = data.get("project_tender_id", data.get("tender_no", ""))
            if not raw_proj_id or str(raw_proj_id).strip().upper() in ["N/A", "NONE", "NULL"]:
                raw_proj_id = context.get("tender_no") or context.get("project_id", "N/A")
            project_id = str(raw_proj_id).strip()

            bg_no = str(data.get("bg_number", "")).strip()
            bg_amount = str(data.get("bg_amount", "")).strip()
            release_status = data.get("release_status", "অবমুক্তি / বিল ছাড়করণ প্রক্রিয়াধীন")
            bank_action = data.get("bank_action", "হিসাব বিভাগের সাথে যোগাযোগ ও ছাড়করণ")

            # Check if this is Tender Security (EMD) release vs BG release vs Bill payment
            subj_lower = str(context.get("subject", "")).lower()
            is_security_emd = any(k in subj_lower for k in ["tender security", "security deposit", "emd", "earnest money"])
            is_bg = bool(bg_no and bg_no.upper() not in ["N/A", "NONE", "NULL"])

            if is_security_emd:
                header_title = "💰 *দরপত্র জামানত (EMD/পে-অর্ডার) অবমুক্তি নোটিফিকেশন*"
                ref_label = "টেন্ডার / প্রজেক্ট রেফারেন্স:"
                amount_label = "অব্যাহতিপ্রাপ্ত জামানতের অংক:"
                bg_line = ""
            elif is_bg:
                header_title = "💰 *জামানত (PG) অবমুক্তি ও ব্যাংক ট্র্যাকিং*"
                ref_label = "প্রজেক্ট / টেন্ডার আইডি:"
                amount_label = "জামানতের (BG) অংক:"
                bg_line = f"• ব্যাংক গ্যারান্টি (BG) নং: `{bg_no}`\n"
            else:
                header_title = "💰 *বকেয়া বিল ট্র্যাকিং ও পরিশোধ তদারকি*"
                ref_label = "বকেয়া বিল / PO রেফারেন্স:"
                amount_label = "দাবিকৃত / প্রদেয় বিলের অংক:"
                bg_line = ""

            if not bg_amount or bg_amount.upper() in ["N/A", "NONE"]:
                bg_amount = "মূল নথি ও চুক্তি অনুযায়ী" if is_security_emd else "বিল ভাউচার ও চুক্তি অনুযায়ী"

            msg = (
                f"{header_title}\n"
                f"🏛️ প্রতিষ্ঠান: *{source}*\n"
                f"{date_line}"
                f"──────────────────────────────\n"
                f"📋 *পেমেন্ট ও হিসাব বিবরণ:*\n"
                f"• {ref_label} `{project_id}`\n"
                f"{bg_line}"
                f"• {amount_label} *{bg_amount}*\n"
                f"• বর্তমান স্ট্যাটাস: {release_status}\n"
                f"• প্রাতিষ্ঠানিক প্রক্রিয়া: {bank_action}\n"
            )
            if data.get('buyer_contact_person') and data.get('buyer_contact_person') != 'N/A':
                msg += f"• যোগাযোগ: {data['buyer_contact_person']}\n"
            msg += (
                f"──────────────────────────────\n"
                f"🏦 *আর্থিক করণীয়:*\n{critical_action}\n"
                f"──────────────────────────────\n"
                f"📧 আবেদনপত্র ও সার্টিফিকেট: {gmail_link}\n"
                f"📊 লাইভ ট্র্যাকার শিট: {sheet_link}"
            )
            return msg

        # Fallback
        return (
            f"🔔 প্রকিউরমেন্ট নোটিফিকেশন ({source})\n"
            f"বিষয়: {data.get('items_summary', 'প্রকিউরমেন্ট আপডেট')}\n"
            f"রেফারেন্স: {data.get('tender_no', 'N/A')}\n"
            f"জরুরি করণীয়: {critical_action}\n"
            f"জিমেইল লিংক: {gmail_link}"
        )

    # ================================================================ #
    # TIER 2: SUPPLIER QUOTATION TEMPLATES                             #
    # ================================================================ #
    @classmethod
    def _format_supplier_alert(cls, stage: str, data: dict, source: str, critical_action: str, gmail_link: str, sheet_link: str, date_line: str = "") -> str:
        supplier_name = data.get("supplier_name", source)
        quoted_items = _clean_bengali_desc(data.get("quoted_items"), "সংযুক্ত ফাইলে বিস্তারিত")
        total_amount = _clean_bengali_desc(data.get("total_quoted_amount"), "কোটেশনে উল্লেখিত")
        lead_time = _clean_bengali_desc(data.get("delivery_lead_time"), "আলোচনা সাপেক্ষে")
        validity = _clean_bengali_desc(data.get("quote_validity"), "উল্লেখ নেই")
        payment_terms = _clean_bengali_desc(data.get("payment_terms"), "উল্লেখ নেই")
        related_ref = _clean_bengali_desc(data.get("related_tender_ref"), "সরাসরি সম্পর্কিত নয়")

        stage_labels = {
            "S1_QUOTE_RECEIVED": ("📩", "সাপ্লায়ার কোটেশন প্রাপ্ত"),
            "S2_UNDER_REVIEW": ("🔄", "কোটেশন রিভিশন / ফলো-আপ"),
            "S3_ORDER_PLACED": ("✅", "সাপ্লায়ারকে অর্ডার প্রদান"),
            "S4_AWAITING_DELIVERY": ("🚢", "সাপ্লায়ার ডেলিভারি ট্র্যাকিং"),
        }
        emoji, title = stage_labels.get(stage, ("📩", "সাপ্লায়ার আপডেট"))

        msg = (
            f"{emoji} *{title}*\n"
            f"🏭 সাপ্লায়ার: *{supplier_name}*\n"
            f"{date_line}"
            f"──────────────────────────────\n"
            f"📋 *কোটেশন বিবরণ:*\n"
            f"• আইটেম: {quoted_items}\n"
            f"• মোট অংক: *{total_amount}*\n"
            f"• ডেলিভারি সময়: {lead_time}\n"
            f"• ভ্যালিডিটি: {validity}\n"
            f"• পেমেন্ট শর্ত: {payment_terms}\n"
            f"• সংশ্লিষ্ট টেন্ডার: {related_ref}\n"
        )
        if data.get('supplier_country') and data.get('supplier_country') != 'N/A':
            msg += f"• দেশ: {data['supplier_country']}\n"
        if data.get('incoterms') and data.get('incoterms') != 'N/A':
            msg += f"• ইনকোটার্মস: {data['incoterms']}\n"
        if data.get('currency') and data.get('currency') != 'N/A':
            msg += f"• মুদ্রা: {data['currency']}\n"
        msg += (
            f"──────────────────────────────\n"
            f"🎯 *করণীয়:*\n{critical_action}\n"
            f"──────────────────────────────\n"
            f"📧 কোটেশন দেখুন: {gmail_link}"
        )
        if sheet_link:
            msg += f"\n📊 লাইভ ট্র্যাকার শিট: {sheet_link}"
        return msg

    # ================================================================ #
    # TIER 3: BANK / TRADE FINANCE TEMPLATES                           #
    # ================================================================ #
    @classmethod
    def _format_bank_alert(cls, stage: str, data: dict, source: str, critical_action: str, gmail_link: str, sheet_link: str, date_line: str = "") -> str:
        bank_name = data.get("bank_name", source)
        doc_type = _clean_bengali_desc(data.get("document_type"), "ব্যাংকিং ডকুমেন্ট")
        lc_number = _clean_bengali_desc(data.get("lc_number"), "রেফারেন্স নেই")
        amount = _clean_bengali_desc(data.get("amount"), "ডকুমেন্টে উল্লেখিত")
        expiry = _clean_bengali_desc(data.get("expiry_date"), "উল্লেখ নেই")
        related_ref = _clean_bengali_desc(data.get("related_tender_ref"), "সরাসরি সম্পর্কিত নয়")

        stage_labels = {
            "B1_LC_DRAFT": ("📝", "এলসি ড্রাফট / সংশোধনী"),
            "B2_LC_OPENED": ("🏦", "এলসি ওপেন / কনফার্ম"),
            "B3_DOCS_SUBMITTED": ("📄", "ব্যাংকিং ডকুমেন্ট জমা"),
            "B4_PAYMENT_RECEIVED": ("💰", "পেমেন্ট / ফান্ড ট্রান্সফার"),
        }
        emoji, title = stage_labels.get(stage, ("🏦", "ব্যাংকিং আপডেট"))

        msg = (
            f"{emoji} *{title}*\n"
            f"🏛️ ব্যাংক: *{bank_name}*\n"
            f"{date_line}"
            f"──────────────────────────────\n"
            f"📋 *ডকুমেন্ট বিবরণ:*\n"
            f"• ডকুমেন্ট টাইপ: {doc_type}\n"
            f"• এলসি / রেফারেন্স নং: `{lc_number}`\n"
            f"• অংক: *{amount}*\n"
            f"• মেয়াদ: {expiry}\n"
            f"• সংশ্লিষ্ট প্রকিউরমেন্ট: {related_ref}\n"
        )
        if stage in ["B1_LC_DRAFT", "B2_LC_OPENED", "B3_DOCS_SUBMITTED"]:
            if data.get('lc_type') and data.get('lc_type') != 'N/A':
                msg += f"• এলসি ধরন: {data['lc_type']}\n"
            if data.get('documents_required') and data.get('documents_required') != 'N/A':
                msg += f"• প্রয়োজনীয় ডকুমেন্টস: {data['documents_required']}\n"
        if stage == "B4_PAYMENT_RECEIVED":
            if data.get('tt_reference_no') and data.get('tt_reference_no') != 'N/A':
                msg += f"• টিটি রেফারেন্স: {data['tt_reference_no']}\n"
        msg += (
            f"──────────────────────────────\n"
            f"🏦 *আর্থিক করণীয়:*\n{critical_action}\n"
            f"──────────────────────────────\n"
            f"📧 ব্যাংক মেইল দেখুন: {gmail_link}"
        )
        if sheet_link:
            msg += f"\n📊 লাইভ ট্র্যাকার শিট: {sheet_link}"
        return msg
