"""
Domain Router — Email Classification Engine
Enterprise Trading Corporation — Business Mail Copilot

Classifies incoming emails into tiers based on sender domain,
specific gmail senders, and subject keyword analysis.

Tiers:
  BUYER    — Power plants, government bodies (Tier 1)
  SUPPLIER — OEMs, manufacturers, trading houses (Tier 2)
  BANK     — Trade finance, LC, SWIFT (Tier 3)
  INTERNAL — Staff / associated company emails
  IGNORE   — Noise, spam, personal, newsletters
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any


class DomainRouter:
    """Classifies emails by sender domain/address into processing tiers."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent / "config" / "domain_routing.json"
        
        with open(config_path, encoding="utf-8") as f:
            self.config = json.load(f)

        # Build fast lookup sets
        self._buyer_domains = set(d.lower() for d in self.config.get("tier_1_buyer", {}).get("domains", []))
        self._buyer_gmail = set(s.lower() for s in self.config.get("tier_1_buyer", {}).get("gmail_senders", []))
        
        self._supplier_domains = set(d.lower() for d in self.config.get("tier_2_supplier", {}).get("domains", []))
        
        self._bank_domains = set(d.lower() for d in self.config.get("tier_3_bank", {}).get("domains", []))
        self._bank_subject_must = [kw.lower() for kw in self.config.get("tier_3_bank", {}).get("subject_must_contain_any", [])]
        self._bank_subject_ignore = [kw.lower() for kw in self.config.get("tier_3_bank", {}).get("subject_ignore_if_contains", [])]
        
        self._internal_gmail = set(s.lower() for s in self.config.get("gmail_internal", {}).get("senders", []))
        
        self._ignore_domains = set(d.lower() for d in self.config.get("ignore_domains", []))

        # Gmail fallback keyword sets
        fb = self.config.get("gmail_fallback", {})
        self._fb_tender = [kw.lower() for kw in fb.get("tender_keywords", [])]
        self._fb_quote = [kw.lower() for kw in fb.get("quotation_keywords", [])]
        self._fb_bank = [kw.lower() for kw in fb.get("banking_keywords", [])]
        self._fb_delivery = [kw.lower() for kw in fb.get("delivery_keywords", [])]
        self._fb_payment = [kw.lower() for kw in fb.get("payment_keywords", [])]

    def extract_domain(self, sender: str) -> str:
        """Extract domain from a From header value like 'Name <email@domain.com>'."""
        match = re.search(r'@([a-zA-Z0-9.\-_]+)', sender)
        return match.group(1).lower() if match else ""

    def extract_email(self, sender: str) -> str:
        """Extract bare email from a From header value."""
        match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', sender)
        return match.group(0).lower() if match else sender.lower().strip()

    def classify(self, sender: str, subject: str = "") -> Dict[str, Any]:
        """
        Classify an email into a processing tier.
        
        Returns:
            {
                "tier": "BUYER" | "SUPPLIER" | "BANK" | "INTERNAL" | "IGNORE",
                "domain": "energy-utility.com",
                "email": "sender@energy-utility.com",
                "confidence": "DOMAIN_MATCH" | "GMAIL_SENDER" | "SUBJECT_KEYWORD" | "DEFAULT"
            }
        """
        domain = self.extract_domain(sender)
        email = self.extract_email(sender)
        subj_lower = subject.lower()

        result = {"domain": domain, "email": email}

        # 1. Check IGNORE list first (highest priority for noise filtering)
        if domain in self._ignore_domains:
            result["tier"] = "IGNORE"
            result["confidence"] = "DOMAIN_MATCH"
            return result

        # 2. Self-sent emails
        if "enterprise.automation@example.com" in email:
            result["tier"] = "IGNORE"
            result["confidence"] = "SELF_SENT"
            return result

        # 3. Tier 1: Buyer domains
        if domain in self._buyer_domains:
            result["tier"] = "BUYER"
            result["confidence"] = "DOMAIN_MATCH"
            return result

        # 4. Tier 1: Specific gmail senders (e.g. powergenprocurement)
        if email in self._buyer_gmail:
            result["tier"] = "BUYER"
            result["confidence"] = "GMAIL_SENDER"
            return result

        # 5. Tier 2: Supplier domains
        if domain in self._supplier_domains:
            result["tier"] = "SUPPLIER"
            result["confidence"] = "DOMAIN_MATCH"
            return result

        # 6. Tier 3: Bank domains (with subject filtering)
        if domain in self._bank_domains:
            # Check if subject matches banking content
            if any(kw in subj_lower for kw in self._bank_subject_ignore):
                result["tier"] = "IGNORE"
                result["confidence"] = "BANK_NOISE_FILTER"
                return result
            if any(kw in subj_lower for kw in self._bank_subject_must):
                result["tier"] = "BANK"
                result["confidence"] = "DOMAIN_MATCH"
                return result
            # Bank domain but no banking keyword in subject — treat as noise
            result["tier"] = "IGNORE"
            result["confidence"] = "BANK_NO_KEYWORD"
            return result

        # 7. Internal staff gmail
        if email in self._internal_gmail:
            result["tier"] = "INTERNAL"
            result["confidence"] = "GMAIL_SENDER"
            return result

        # 8. Unknown gmail.com — fallback to subject keyword analysis
        if domain == "gmail.com":
            if any(kw in subj_lower for kw in self._fb_tender):
                result["tier"] = "BUYER"
                result["confidence"] = "SUBJECT_KEYWORD"
                return result
            if any(kw in subj_lower for kw in self._fb_quote):
                result["tier"] = "SUPPLIER"
                result["confidence"] = "SUBJECT_KEYWORD"
                return result
            if any(kw in subj_lower for kw in self._fb_bank):
                result["tier"] = "BANK"
                result["confidence"] = "SUBJECT_KEYWORD"
                return result
            if any(kw in subj_lower for kw in self._fb_delivery + self._fb_payment):
                result["tier"] = "BUYER"
                result["confidence"] = "SUBJECT_KEYWORD"
                return result
            # Unknown gmail with no keyword match
            result["tier"] = "IGNORE"
            result["confidence"] = "GMAIL_NO_KEYWORD"
            return result

        # 9. Completely unknown domain — default IGNORE
        result["tier"] = "IGNORE"
        result["confidence"] = "UNKNOWN_DOMAIN"
        return result
