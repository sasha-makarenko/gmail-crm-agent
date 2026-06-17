"""
Ultra-Simple LLM Processor for Gmail Thread Analysis

This module provides a very simple LLM processing system that focuses on
basic lead detection without complex parsing.
"""

import os
import re
from typing import Dict, List, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

class UltraSimpleLLMProcessor:
    """Ultra-simple LLM processor focused on basic lead detection."""
    
    # Company information for filtering
    COMPANY_EMAILS = ["info@sweet-sdpearls.de", "hello.sdpearls@gmail.com"]
    COMPANY_NAMES = ["SD Pearls", "Sweet SD Pearls"]
    COMPANY_PEOPLE = ["Nataliia Makarenko", "Nataliia", "Makarenko", "Наталия Макаренко", "Наталія Макаренко"]
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """Initialize Ultra-Simple LLM processor."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        # Initialize LangChain components
        self.model = ChatOpenAI(
            api_key=self.api_key,
            model=model,
            temperature=0.1,
            max_retries=3,
            request_timeout=30
        )
        
        # Create simple prompt
        self._create_prompt()
    
    def _create_prompt(self):
        """Create ultra-simple prompt."""
        self.classification_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are analyzing emails for SD Pearls, a European manufacturer of sugar sprinkles and edible cake decorations.

Your task is to identify ANY potential business opportunities. Be VERY INCLUSIVE - it's better to capture a potential lead than to miss one.

CLASSIFY AS A LEAD if the email contains ANY of the following:
- Questions about products, services, or business
- Requests for information, quotes, catalogs, samples
- Any communication from a real person (not automated systems)
- Any inquiry, question, or request
- Any follow-up or response to previous communications
- Any communication that could potentially lead to a sale
- Any business-related discussion
- Any mention of products, orders, deliveries, payments
- Any communication that seems like it could be from a customer or potential customer

ONLY REJECT if the email is clearly:
- Automated system messages (noreply, no-reply, system notifications)
- Pure spam or completely irrelevant content
- Internal company communications from SD Pearls team

IMPORTANT: 
- Be VERY INCLUSIVE
- When in doubt, classify as A LEAD
- Include ANY email from a real person
- Include ANY business-related communication

Respond with ONLY one word: "LEAD" or "NOT_LEAD"
"""),
            ("user", "Analyze this email: {thread_text}")
        ])
    
    def _is_company_email(self, thread_text: str, headers: Dict[str, str]) -> bool:
        """Check if this is an email from our company."""
        from_email = headers.get("From", "").lower()
        
        # Only filter out if it's EXACTLY from our company emails
        if any(company_email.lower() == from_email.lower() for company_email in self.COMPANY_EMAILS):
            return True
        
        return False
    
    def _is_obvious_spam(self, thread_text: str, headers: Dict[str, str]) -> bool:
        """Check if this is obvious spam."""
        text_lower = thread_text.lower()
        from_email = headers.get("From", "").lower()
        
        # Check for noreply emails
        if any(noreply in from_email for noreply in ["noreply@", "no-reply@", "noreply.", "no-reply."]):
            return True
        
        # Check for obvious spam patterns
        obvious_spam_patterns = [
            "work.ua", "tickets.ua", "qonto.com", "pati-versand.de", 
            "kff-group.com", "eurodix.fr", "linbraze.com"
        ]
        
        if any(pattern in text_lower for pattern in obvious_spam_patterns):
            return True
        
        return False
    
    def _extract_basic_info(self, thread_text: str, headers: Dict[str, str]) -> Dict[str, str]:
        """Extract basic information using simple regex patterns."""
        # Extract email from headers first
        email = ""
        for field in ["From", "Reply-To", "Return-Path"]:
            if field in headers:
                header_value = headers[field]
                if "@" in header_value:
                    parts = header_value.split()
                    for part in parts:
                        if "@" in part and "." in part:
                            email = part.strip("<>\"'")
                            if "@" in email and "." in email:
                                break
                if email:
                    break
        
        # If no email in headers, try to extract from text
        if not email:
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, thread_text)
            if emails:
                email = emails[0]
        
        # Extract name from headers
        name = ""
        if headers:
            from_field = headers.get("From", "")
            if "<" in from_field and ">" in from_field:
                name = from_field.split("<")[0].strip().strip('"')
        
        # Extract phone number
        phone = ""
        phone_pattern = r'(\+?[\d\s\-\(\)]{10,})'
        phones = re.findall(phone_pattern, thread_text)
        if phones:
            phone = phones[0].strip()
        
        return {
            "email": email,
            "name": name,
            "company": "",
            "phone": phone,
            "language": "unknown",
            "country": "",
            "business_type": "",
            "interest": ""
        }
    
    def classify_thread(self, thread_text: str) -> bool:
        """Classify the email as a lead or not."""
        try:
            # Create the classification chain
            classification_chain = self.classification_prompt | self.model
            
            result = classification_chain.invoke({
                "thread_text": thread_text[:4000]
            })
            
            # Parse the simple response
            response = result.content.strip().upper()
            return "LEAD" in response
            
        except Exception as e:
            print(f"Error in lead classification: {e}")
            # Default to LEAD on error (be inclusive)
            return True
    
    def process_thread(self, thread_id: str, thread_text: str, headers: Dict[str, str]) -> Dict:
        """
        Process a single email thread.
        
        Args:
            thread_id: Gmail thread ID
            thread_text: Email thread text
            headers: Email headers
            
        Returns:
            Processing result dictionary
        """
        try:
            # Check if this is a company email
            if self._is_company_email(thread_text, headers):
                return {
                    "status": "skip",
                    "thread_id": thread_id,
                    "reason": "Company email - filtered out"
                }
            
            # Check if this is obvious spam
            if self._is_obvious_spam(thread_text, headers):
                return {
                    "status": "skip",
                    "thread_id": thread_id,
                    "reason": "Obvious spam - filtered out"
                }
            
            # Classify the thread
            is_lead = self.classify_thread(thread_text)
            
            if not is_lead:
                return {
                    "status": "skip",
                    "thread_id": thread_id,
                    "reason": "Not classified as lead"
                }
            
            # Extract basic contact information
            contact_info = self._extract_basic_info(thread_text, headers)
            
            if not contact_info["email"]:
                return {
                    "status": "error",
                    "thread_id": thread_id,
                    "error_message": "No email address found"
                }
            
            return {
                "status": "success",
                "thread_id": thread_id,
                "contact_info": contact_info
            }
            
        except Exception as e:
            return {
                "status": "error",
                "thread_id": thread_id,
                "error_message": f"Processing failed: {e}"
            }



