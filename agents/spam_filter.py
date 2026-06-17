"""
Spam Filter Module for Gmail CRM Agent

This module provides spam/denylist filtering BEFORE LLM classification
to reduce API costs and improve processing speed.
"""

import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class SpamCheckResult:
    """Result of spam check."""

    is_spam: bool
    reason: str
    matched_rule: Optional[str] = None


class SpamFilter:
    """Spam filter using denylist rules from YAML configuration."""

    def __init__(self, rules_path: Path):
        """
        Initialize spam filter with rules from YAML file.

        Args:
            rules_path: Path to spam_rules.yaml file
        """
        self.rules_path = rules_path
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict:
        """Load spam rules from YAML file."""
        if not self.rules_path.exists():
            # Return default minimal rules if file doesn't exist
            return {
                "allowlist": {"emails": [], "domains": []},
                "denylist_emails": [],
                "denylist_domains": [],
                "denylist_regex": [],
                "company": {"emails": [], "domains": [], "names": []},
            }

        try:
            with open(self.rules_path, "r", encoding="utf-8") as f:
                rules = yaml.safe_load(f) or {}

            # Ensure all expected keys exist
            rules.setdefault("allowlist", {"emails": [], "domains": []})
            rules.setdefault("denylist_emails", [])
            rules.setdefault("denylist_domains", [])
            rules.setdefault("denylist_regex", [])
            rules.setdefault("company", {"emails": [], "domains": [], "names": []})

            return rules
        except Exception as e:
            print(f"Warning: Could not load spam rules from {self.rules_path}: {e}")
            return {
                "allowlist": {"emails": [], "domains": []},
                "denylist_emails": [],
                "denylist_domains": [],
                "denylist_regex": [],
                "company": {"emails": [], "domains": [], "names": []},
            }

    def _extract_email_from_header(self, header_value: str) -> str:
        """
        Extract email address from header value like 'Name <email@domain.com>'.

        Args:
            header_value: Header value string

        Returns:
            Extracted email address or original string
        """
        if not header_value:
            return ""

        # Look for email in angle brackets
        match = re.search(r"<([^>]+)>", header_value)
        if match:
            return match.group(1).strip().lower()

        # Look for email pattern
        match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", header_value)
        if match:
            return match.group(0).strip().lower()

        return header_value.strip().lower()

    def _extract_domain(self, email: str) -> str:
        """
        Extract domain from email address.

        Args:
            email: Email address

        Returns:
            Domain part of email
        """
        if "@" in email:
            return email.split("@")[1].lower()
        return ""

    def check_allowlist(self, from_email: str, headers: Dict[str, str]) -> bool:
        """
        Check if email is in allowlist (should never be marked as spam).

        Args:
            from_email: From email address
            headers: Email headers

        Returns:
            True if in allowlist
        """
        allowlist = self.rules.get("allowlist", {})
        allowed_emails = [e.lower() for e in allowlist.get("emails", [])]
        allowed_domains = [d.lower() for d in allowlist.get("domains", [])]

        # Check exact email match
        if from_email.lower() in allowed_emails:
            return True

        # Check domain match
        domain = self._extract_domain(from_email)
        if any(allowed_domain in domain for allowed_domain in allowed_domains):
            return True

        return False

    def check_denylist_email(self, from_email: str) -> SpamCheckResult:
        """
        Check if email is in denylist (exact match).

        Args:
            from_email: From email address

        Returns:
            SpamCheckResult
        """
        denylist = [e.lower() for e in self.rules.get("denylist_emails", [])]

        email_lower = from_email.lower()
        for denied_email in denylist:
            if denied_email in email_lower or email_lower == denied_email:
                return SpamCheckResult(
                    is_spam=True,
                    reason="Denylist: email match",
                    matched_rule=denied_email,
                )

        return SpamCheckResult(is_spam=False, reason="Not in email denylist")

    def check_denylist_domain(self, from_email: str) -> SpamCheckResult:
        """
        Check if email domain is in denylist.

        Args:
            from_email: From email address

        Returns:
            SpamCheckResult
        """
        denylist = [d.lower() for d in self.rules.get("denylist_domains", [])]
        domain = self._extract_domain(from_email)

        for denied_domain in denylist:
            if denied_domain in domain:
                return SpamCheckResult(
                    is_spam=True,
                    reason="Denylist: domain match",
                    matched_rule=denied_domain,
                )

        return SpamCheckResult(is_spam=False, reason="Not in domain denylist")

    def check_denylist_regex(
        self, subject: str, from_header: str, thread_text: str
    ) -> SpamCheckResult:
        """
        Check if content matches denylist regex patterns.

        Args:
            subject: Email subject
            from_header: From header
            thread_text: Email body text

        Returns:
            SpamCheckResult
        """
        regex_rules = self.rules.get("denylist_regex", [])

        # Combine all searchable content
        combined_text = f"{subject}\n{from_header}\n{thread_text[:1000]}"

        for rule in regex_rules:
            if not isinstance(rule, dict):
                continue

            pattern = rule.get("pattern", "")
            case_insensitive = rule.get("case_insensitive", False)
            reason_suffix = rule.get("reason", "regex match")

            if not pattern:
                continue

            flags = re.IGNORECASE if case_insensitive else 0
            try:
                if re.search(pattern, combined_text, flags):
                    return SpamCheckResult(
                        is_spam=True,
                        reason=f"Denylist: {reason_suffix}",
                        matched_rule=pattern,
                    )
            except re.error:
                # Skip invalid regex patterns
                continue

        return SpamCheckResult(is_spam=False, reason="Not matched by regex denylist")

    def check_company_email(self, from_email: str, from_header: str, thread_text: str) -> SpamCheckResult:
        """
        Check if email is from our company (should be skipped).

        Args:
            from_email: From email address
            from_header: From header value
            thread_text: Email body text

        Returns:
            SpamCheckResult
        """
        company = self.rules.get("company", {})
        company_emails = [e.lower() for e in company.get("emails", [])]
        company_domains = [d.lower() for d in company.get("domains", [])]
        company_names = [n.lower() for n in company.get("names", [])]

        # Check exact email match
        if from_email.lower() in company_emails:
            return SpamCheckResult(
                is_spam=True,
                reason="Company email: outgoing mail",
                matched_rule=from_email,
            )

        # Check domain match
        domain = self._extract_domain(from_email)
        for company_domain in company_domains:
            if company_domain in domain:
                # Additional check: make sure it's FROM us, not TO us
                from_lower = from_header.lower()
                if any(ce in from_lower for ce in company_emails):
                    return SpamCheckResult(
                        is_spam=True,
                        reason="Company email: outgoing mail",
                        matched_rule=company_domain,
                    )

        # Check company names in From header
        from_lower = from_header.lower()
        for company_name in company_names:
            if company_name in from_lower:
                # Make sure it's actually FROM us
                if any(ce in from_lower for ce in company_emails):
                    return SpamCheckResult(
                        is_spam=True,
                        reason="Company email: outgoing mail",
                        matched_rule=company_name,
                    )

        return SpamCheckResult(is_spam=False, reason="Not a company email")

    def is_spam(
        self,
        from_email: str,
        headers: Dict[str, str],
        subject: str,
        thread_text: str,
    ) -> SpamCheckResult:
        """
        Main spam check function - applies all rules in order.

        Args:
            from_email: From email address (extracted)
            headers: Full email headers dictionary
            subject: Email subject
            thread_text: Email body text

        Returns:
            SpamCheckResult with is_spam boolean and reason

        Rule order:
            1. Allowlist (if matched, NOT spam)
            2. Company emails (if matched, IS spam)
            3. Denylist emails (if matched, IS spam)
            4. Denylist domains (if matched, IS spam)
            5. Denylist regex (if matched, IS spam)
        """
        from_header = headers.get("From", "")

        # 1. Check allowlist first (highest priority - never spam)
        if self.check_allowlist(from_email, headers):
            return SpamCheckResult(
                is_spam=False,
                reason="Allowlist: trusted sender",
                matched_rule=from_email,
            )

        # 2. Check company emails (outgoing mail - should skip)
        result = self.check_company_email(from_email, from_header, thread_text)
        if result.is_spam:
            return result

        # 3. Check denylist emails
        result = self.check_denylist_email(from_email)
        if result.is_spam:
            return result

        # 4. Check denylist domains
        result = self.check_denylist_domain(from_email)
        if result.is_spam:
            return result

        # 5. Check denylist regex patterns
        result = self.check_denylist_regex(subject, from_header, thread_text)
        if result.is_spam:
            return result

        # Not spam by denylist rules
        return SpamCheckResult(is_spam=False, reason="Passed denylist checks")


def load_spam_filter(rules_path: Path) -> SpamFilter:
    """
    Load spam filter from rules file.

    Args:
        rules_path: Path to spam_rules.yaml

    Returns:
        SpamFilter instance
    """
    return SpamFilter(rules_path)
