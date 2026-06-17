"""
LLM Processor for Gmail Thread Analysis

This module provides LLM-based functions for classifying email threads,
extracting contact information, and generating summaries. Supports both
OpenAI and Anthropic providers.
"""

import os
import json
from typing import Dict, Any, Optional, Literal
from openai import OpenAI
import anthropic


class LLMProcessor:
    """LLM processor for email thread analysis with multi-provider support."""

    def __init__(
        self,
        provider: Optional[Literal["openai", "anthropic"]] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize LLM processor.

        Args:
            provider: LLM provider ("openai" or "anthropic")
            api_key: API key (if not provided, will use env var)
            model: Model name (if not provided, will use defaults)
        """
        self.provider = provider or os.getenv("MODEL_PROVIDER", "openai").lower()

        if self.provider not in ["openai", "anthropic"]:
            raise ValueError(f"Invalid provider: {self.provider}. Must be 'openai' or 'anthropic'.")

        # Initialize the appropriate client
        if self.provider == "openai":
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OpenAI API key is required")
            self.client = OpenAI(api_key=self.api_key)
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        else:  # anthropic
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise ValueError("Anthropic API key is required")
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    def _call_llm(self, system_prompt: str, user_prompt: str, json_mode: bool = True) -> str:
        """
        Call LLM with unified interface for both providers.

        Args:
            system_prompt: System/context prompt
            user_prompt: User message
            json_mode: Whether to expect JSON response

        Returns:
            LLM response text
        """
        if self.provider == "openai":
            kwargs = {
                "model": self.model,
                "temperature": 0.1,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content

        else:  # anthropic
            # Anthropic doesn't have native JSON mode, so we include it in the prompt
            if json_mode:
                system_prompt += "\n\nIMPORTANT: Respond ONLY with valid JSON. No other text."

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=0.1,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text

    def classify_thread(self, thread_text: str) -> Dict[str, Any]:
        """
        Classify if a thread contains a potential lead.
        CONSERVATIVE approach: only mark as spam if clearly not a business inquiry.

        Args:
            thread_text: Email thread text

        Returns:
            Classification result with is_lead boolean and reason
        """
        try:
            system_prompt = """You are a business development specialist for SD Pearls, a company selling cake decorating supplies, sprinkles, and baking tools.

Your task is to identify potential business opportunities and customer inquiries. Be CONSERVATIVE about marking things as spam - when in doubt, classify as a lead.

CLASSIFY AS LEAD (is_lead: true) if the email contains ANY of:
- Product inquiries (questions about items, prices, availability)
- Order requests or purchase interest
- Questions about shipping, delivery, or international orders
- Wholesale, bulk order, or partnership inquiries
- Customer service questions (order status, returns, support)
- Requests for catalogs, samples, or product information
- Questions from bakeries, cafes, or businesses
- Any legitimate customer communication

CLASSIFY AS NOT A LEAD (is_lead: false) ONLY if CLEARLY:
- Automated marketing/newsletters (unsubscribe links, mass marketing)
- Social media notifications (LinkedIn, Facebook, etc.)
- Automated system messages (delivery confirmations from carriers, password resets)
- Job applications or recruitment spam
- Financial/banking notifications
- Completely unrelated spam (cryptocurrency, loans, etc.)

IMPORTANT:
- Language doesn't matter - business in any language is a lead
- Brief inquiries are still leads
- Follow-up messages from customers are leads
- When uncertain, classify as LEAD (better false positive than false negative)
- Only mark as spam if you're very confident it's not business-related

Respond with JSON:
{
    "is_lead": true/false,
    "reason": "clear explanation of classification",
    "confidence": "high/medium/low"
}"""

            user_prompt = f"Classify this email thread:\n\n{thread_text[:4000]}"

            response_text = self._call_llm(system_prompt, user_prompt, json_mode=True)

            # Parse response
            try:
                result = json.loads(response_text)
                return {
                    "is_lead": result.get("is_lead", True),  # Default to lead on parsing issues
                    "reason": result.get("reason", "Classification completed"),
                    "confidence": result.get("confidence", "medium"),
                }
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse classification response: {e}")
                # Conservative fallback: treat as lead
                return {
                    "is_lead": True,
                    "reason": "Parse error - defaulting to lead for manual review",
                    "confidence": "low",
                }

        except Exception as e:
            print(f"Error in lead classification: {e}")
            # Conservative fallback: treat as lead
            return {
                "is_lead": True,
                "reason": f"Classification error: {e} - manual review recommended",
                "confidence": "low",
            }

    def extract_contact(self, thread_text: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Extract contact information from email thread.

        Args:
            thread_text: Email thread text
            headers: Email headers (for better email extraction)

        Returns:
            Dictionary with contact information (company, address, website, lpr_name, lpr_phone, lpr_email)
        """
        try:
            # Extract email from headers if available
            extracted_email = ""
            if headers:
                from_header = headers.get("From", "")
                if "@" in from_header:
                    # Extract email from "Name <email@domain.com>" format
                    import re
                    match = re.search(r"<([^>]+)>", from_header)
                    if match:
                        extracted_email = match.group(1).strip()
                    else:
                        match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", from_header)
                        if match:
                            extracted_email = match.group(0).strip()

            system_prompt = """You are an expert at extracting structured contact information from emails in multiple languages.

Extract ALL available information and return as strict JSON with these exact fields (use empty string "" if not found):

{
    "company": "Company name (if mentioned)",
    "address": "Physical address (if mentioned)",
    "website": "Website URL (if mentioned)",
    "lpr_name": "Contact person's full name (LPR = Lead Point of Responsibility)",
    "lpr_phone": "Phone number in international format (if mentioned)",
    "lpr_email": "Email address (extract from signature or body)"
}

IMPORTANT:
- Extract information in ANY language (English, Russian, German, etc.)
- Use empty string "" for fields not found (never use null or omit fields)
- lpr_email: Look for email in signature, body, or reply-to
- lpr_name: Extract from signature, "Best regards, Name", or email name field
- company: Look for business names, company signatures
- Format phone numbers with country code if possible (+1, +49, +7, etc.)
- Return ONLY valid JSON, no other text"""

            user_prompt = f"Extract contact information from this email:\n\n{thread_text[:4000]}"

            response_text = self._call_llm(system_prompt, user_prompt, json_mode=True)

            try:
                result = json.loads(response_text)

                # Use header email if LLM didn't find one
                if not result.get("lpr_email") and extracted_email:
                    result["lpr_email"] = extracted_email

                # Ensure all required fields exist
                return {
                    "company": result.get("company", ""),
                    "address": result.get("address", ""),
                    "website": result.get("website", ""),
                    "lpr_name": result.get("lpr_name", ""),
                    "lpr_phone": result.get("lpr_phone", ""),
                    "lpr_email": result.get("lpr_email", extracted_email),
                }
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse contact extraction: {e}")
                return {
                    "company": "",
                    "address": "",
                    "website": "",
                    "lpr_name": "",
                    "lpr_phone": "",
                    "lpr_email": extracted_email,
                }

        except Exception as e:
            print(f"Error in contact extraction: {e}")
            return {
                "company": "",
                "address": "",
                "website": "",
                "lpr_name": "",
                "lpr_phone": "",
                "lpr_email": extracted_email if "extracted_email" in locals() else "",
            }

    def summarize_thread(self, thread_text: str, existing_notes: Optional[str] = None) -> Dict[str, str]:
        """
        Generate a concise summary of the email thread for Notes field.

        Args:
            thread_text: Email thread text
            existing_notes: Existing notes (if updating a lead)

        Returns:
            Dictionary with 'notes' field containing 1-2 sentence summary
        """
        try:
            if existing_notes:
                system_prompt = f"""You are summarizing an email thread to UPDATE existing notes for a business lead.

EXISTING NOTES:
{existing_notes}

Your task: Add a brief 1-2 sentence update about this NEW communication. Focus on:
- What's new or different from existing notes
- Key customer requests or questions
- Important business details not already captured

Format: Keep it concise and actionable. Merge with existing context, don't repeat information.
Language: Write in the same language as existing notes (likely Russian).
Output: Return ONLY the updated/merged notes text, no JSON wrapper needed."""

                user_prompt = f"Update notes based on this new email:\n\n{thread_text[:4000]}"

                # For note updates, we don't need JSON mode
                response_text = self._call_llm(system_prompt, user_prompt, json_mode=False)
                return {"notes": response_text.strip()}

            else:
                system_prompt = """You are creating a concise business summary for a CRM system.

Create a 1-2 sentence summary in RUSSIAN that captures:
- What the customer wants/needs
- Their business type (if mentioned: bakery, cafe, retail, individual)
- Key product interests or requirements
- Order type (wholesale, retail, bulk) if mentioned

Format: Clear, concise, actionable. Focus on business value.
Language: RUSSIAN ONLY
Length: 1-2 sentences maximum

Return JSON:
{
    "notes": "Your 1-2 sentence Russian summary here"
}"""

                user_prompt = f"Summarize this email thread for CRM notes:\n\n{thread_text[:4000]}"

                response_text = self._call_llm(system_prompt, user_prompt, json_mode=True)

                try:
                    result = json.loads(response_text)
                    return {"notes": result.get("notes", "Требуется ручная проверка.")}
                except json.JSONDecodeError:
                    # If JSON parsing fails, use the raw text (might be Anthropic)
                    return {"notes": response_text.strip() or "Требуется ручная проверка."}

        except Exception as e:
            print(f"Error in summary generation: {e}")
            return {"notes": f"Ошибка анализа: {str(e)}. Требуется ручная проверка."}


# Legacy compatibility function
def analyze_thread(full_text: str, headers: dict, subject: str) -> Dict[str, Any]:
    """Legacy function - use LLMProcessor class instead."""
    processor = LLMProcessor()

    # Combine classification, extraction, and summary
    classification = processor.classify_thread(full_text)
    contact_info = processor.extract_contact(full_text, headers)
    summary = processor.summarize_thread(full_text)

    return {
        "is_lead": classification["is_lead"],
        "reason": classification["reason"],
        "email": contact_info.get("lpr_email"),
        "name": contact_info.get("lpr_name"),
        "company": contact_info.get("company"),
        "phone": contact_info.get("lpr_phone"),
        "notes": summary.get("notes"),
    }
