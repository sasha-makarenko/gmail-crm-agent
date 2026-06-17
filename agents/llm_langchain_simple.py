"""
Simplified LangChain-based LLM Processor for Gmail Thread Analysis

This module provides a robust LLM processing system using LangChain
for better error handling, structured outputs, and reliability.
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, Field, validator

class ContactInfo(BaseModel):
    """Contact information extracted from email thread."""
    email: str = Field(description="Email address")
    name: str = Field(description="Contact name")
    company: str = Field(description="Company name")
    phone: str = Field(description="Phone number")
    language: str = Field(description="Language of the email")
    country: str = Field(description="Country name")
    business_type: str = Field(description="Type of business (bakery, cafe, etc.)")
    interest: str = Field(description="What they're interested in")

class LeadClassification(BaseModel):
    """Lead classification result with confidence scoring."""
    is_lead: bool = Field(description="Whether this is a business lead")
    reason: str = Field(description="Reason for classification decision")
    confidence: float = Field(description="Confidence score (0.0-1.0)", ge=0.0, le=1.0)
    lead_type: str = Field(description="Type of lead (inquiry, order, partnership, etc.)")
    urgency: str = Field(description="Urgency level (low, medium, high)")
    language: str = Field(description="Primary language of the email")

class ThreadSummary(BaseModel):
    """Thread summary result."""
    notes: str = Field(description="Concise summary in Russian (3-4 sentences)")
    key_points: List[str] = Field(description="Key business points")
    next_steps: List[str] = Field(description="Recommended next steps")
    priority: str = Field(description="Priority level (low, medium, high)")

class LangChainLLMProcessor:
    """Modern LLM processor using LangChain for robust processing."""
    
    # Company information for filtering
    COMPANY_EMAILS = ["info@sweet-sdpearls.de", "hello.sdpearls@gmail.com"]
    COMPANY_NAMES = ["SD Pearls", "Sweet SD Pearls"]
    COMPANY_PEOPLE = ["Nataliia Makarenko", "Nataliia", "Makarenko"]
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize LangChain LLM processor.
        
        Args:
            api_key: OpenAI API key
            model: Model to use for processing
        """
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
        
        # Initialize output parsers
        self.classification_parser = PydanticOutputParser(pydantic_object=LeadClassification)
        self.contact_parser = PydanticOutputParser(pydantic_object=ContactInfo)
        self.summary_parser = PydanticOutputParser(pydantic_object=ThreadSummary)
        
        # Create prompt templates
        self._create_prompt_templates()
    
    def _create_prompt_templates(self):
        """Create prompt templates for different tasks."""
        
        # Lead classification prompt
        self.classification_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert business development specialist for SD Pearls, a company that sells cake decorating supplies, sprinkles, and tools.

Your task is to identify ANY potential business opportunity or customer inquiry. Be VERY SENSITIVE and inclusive - it's better to catch a potential lead than miss one.

CLASSIFY AS A LEAD if the email contains ANY of these indicators:

🔍 **Business Inquiries** (any language):
- Questions about products, prices, shipping, availability
- Requests for catalogs, samples, quotes
- Interest in bulk orders, wholesale, partnerships
- Inquiries about specific products (sprinkles, tools, decorations)
- Questions about shipping to specific countries
- Requests for recommendations or advice

🌍 **International Interest** (any language):
- Emails in Russian, Ukrainian, German, English, etc.
- Questions about international shipping
- Interest from foreign customers
- Language doesn't matter - business intent does

💼 **Business Opportunities**:
- Partnership proposals
- Wholesale inquiries
- Bulk order requests
- Retail store inquiries
- Event/catering business inquiries
- Bakery/cafe supply requests

📧 **Customer Service**:
- Order status inquiries
- Product questions
- Shipping questions
- Return/exchange requests
- Technical support questions

🎯 **Specific Product Interest**:
- Sprinkles, sugar decorations
- Cake decorating tools
- Baking supplies
- Party decorations
- Seasonal collections

ONLY CLASSIFY AS SKIP if:
- It's clearly spam (unrelated to food/baking)
- It's an automated system message
- It's a newsletter subscription/unsubscription
- It's a delivery notification (not a customer inquiry)

IMPORTANT: Be VERY INCLUSIVE. When in doubt, classify as a LEAD.
Language barriers should NOT prevent lead identification.
Even brief inquiries should be considered leads.

{format_instructions}"""),
            ("user", "Analyze this email thread for business opportunities:\n\n{thread_text}")
        ])
        
        # Contact extraction prompt
        self.contact_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at extracting contact information from emails in multiple languages.

Extract ALL available contact information from the email thread. Look for:

🔍 **Contact Details** (in any language):
- Email addresses (if not already found in headers)
- Names (first, last, full)
- Company names
- Phone numbers
- Addresses/countries
- Language preferences

🌍 **Language Detection**:
- Identify the primary language of the email
- Note if multiple languages are used
- Common languages: Russian, Ukrainian, German, English, etc.

💼 **Business Context**:
- What they're interested in
- Their business type (bakery, cafe, retail, etc.)
- Order size (retail, wholesale, bulk)
- Specific products mentioned

IMPORTANT: 
- Extract information in ANY language
- Be thorough - extract everything you can find
- If information is missing, use empty string
- Preserve original language when possible
- Focus on finding email addresses if they exist in the text

{format_instructions}"""),
            ("user", "Extract contact information from this email:\n\n{thread_text}")
        ])
        
        # Summary generation prompt
        self.summary_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert business analyst for SD Pearls. Create a comprehensive but CONCISE summary in Russian.

📝 **Summary Requirements**:
- Language: RUSSIAN ONLY
- Length: 3-4 sentences maximum
- Focus: Business opportunity and customer needs
- Structure: Clear, actionable information

🎯 **Include**:
- What the customer wants/needs
- Their business type (if mentioned)
- Specific products of interest
- Order size (retail/wholesale/bulk)
- Any special requirements
- Language they wrote in

📊 **Format** (in Russian):
КРАТКОЕ ОПИСАНИЕ:
[3-4 sentences summarizing the business opportunity]

IMPORTANT: Keep it SHORT and FOCUSED. Don't repeat obvious information.
Extract the key business value from the communication.

{format_instructions}"""),
            ("user", "Summarize this email thread in Russian:\n\n{thread_text}")
        ])
    
    def _is_company_email(self, thread_text: str, headers: Dict[str, str]) -> bool:
        """Check if this is an email from our company."""
        # Check from email in headers
        from_email = headers.get("From", "").lower()
        
        # Only filter out if it's EXACTLY from our company emails
        if any(company_email.lower() == from_email.lower() for company_email in self.COMPANY_EMAILS):
            return True
        
        # Check for company names in the "From" field specifically
        from_field = headers.get("From", "")
        if any(company_name.lower() in from_field.lower() for company_name in self.COMPANY_NAMES):
            if any(company_email.lower() in from_field.lower() for company_email in self.COMPANY_EMAILS):
                return True
        
        # Check if Nataliia is mentioned as sender in the From field
        if any(person.lower() in from_field.lower() for person in self.COMPANY_PEOPLE):
            if any(company_email.lower() in from_field.lower() for company_email in self.COMPANY_EMAILS):
                return True
        
        # Check for company-specific phrases that indicate OUTGOING company emails
        thread_lower = thread_text.lower()
        
        # Only filter if it's clearly an outgoing company announcement
        company_announcement_phrases = [
            "dear partner", "we're excited to share", "we invite our partners", 
            "our halloween collection", "our new products", "we offer",
            "please find attached", "we're launching", "our team"
        ]
        
        # Must have BOTH company phrases AND company identification
        has_company_phrases = any(phrase in thread_lower for phrase in company_announcement_phrases)
        has_company_identification = any(company_name.lower() in thread_lower for company_name in self.COMPANY_NAMES)
        
        if has_company_phrases and has_company_identification:
            if any(phrase in thread_lower for phrase in ["we", "our", "us", "company", "team"]):
                return True
        
        # Check for job application responses from company
        if "отклик на вакансию" in thread_lower or "job application" in thread_lower:
            if any(company_name.lower() in thread_lower for company_name in self.COMPANY_NAMES):
                if any(company_email.lower() in from_field.lower() for company_email in self.COMPANY_EMAILS):
                    return True
        
        return False
    
    def _extract_email_from_headers(self, headers: Dict[str, str]) -> str:
        """Extract email address from headers."""
        for field in ["From", "Reply-To", "Return-Path"]:
            if field in headers:
                header_value = headers[field]
                if "@" in header_value:
                    parts = header_value.split()
                    for part in parts:
                        if "@" in part and "." in part:
                            email = part.strip("<>\"'")
                            if "@" in email and "." in email:
                                return email
        return ""
    
    def classify_thread(self, thread_text: str) -> LeadClassification:
        """Classify the email as a lead or not using LangChain."""
        try:
            # Create the classification chain
            classification_chain = (
                self.classification_prompt.partial(
                    format_instructions=self.classification_parser.get_format_instructions()
                )
                | self.model
                | self.classification_parser
            )
            
            result = classification_chain.invoke({
                "thread_text": thread_text[:4000]
            })
            
            return result
            
        except OutputParserException as e:
            # Fallback to manual parsing
            print(f"Warning: Classification parsing failed, using fallback: {e}")
            return LeadClassification(
                is_lead=True,  # Default to lead on parsing error
                reason="Classification parsing error - manual review recommended",
                confidence=0.5,
                lead_type="unknown",
                urgency="medium",
                language="unknown"
            )
        except Exception as e:
            print(f"Error in lead classification: {e}")
            return LeadClassification(
                is_lead=True,  # Default to lead on error
                reason=f"Classification error: {e} - manual review recommended",
                confidence=0.3,
                lead_type="unknown",
                urgency="medium",
                language="unknown"
            )
    
    def extract_contact(self, thread_text: str, headers: Dict[str, str] = None) -> ContactInfo:
        """Extract contact information using LangChain."""
        try:
            # First, try to extract email from headers
            extracted_email = self._extract_email_from_headers(headers or {})
            
            # Create the contact extraction chain
            contact_chain = (
                self.contact_prompt.partial(
                    format_instructions=self.contact_parser.get_format_instructions()
                )
                | self.model
                | self.contact_parser
            )
            
            result = contact_chain.invoke({
                "thread_text": thread_text[:4000]
            })
            
            # Use extracted email from headers if available
            if extracted_email:
                result.email = extracted_email
            
            return result
            
        except Exception as e:
            print(f"Error in contact extraction: {e}")
            return ContactInfo(
                email=extracted_email if 'extracted_email' in locals() else "",
                name="", company="", phone="", language="", 
                country="", business_type="", interest=""
            )
    
    def summarize_thread(self, thread_text: str) -> ThreadSummary:
        """Generate Russian summary using LangChain."""
        try:
            # Create the summary chain
            summary_chain = (
                self.summary_prompt.partial(
                    format_instructions=self.summary_parser.get_format_instructions()
                )
                | self.model
                | self.summary_parser
            )
            
            result = summary_chain.invoke({
                "thread_text": thread_text[:4000]
            })
            
            # Ensure the summary starts with the Russian header
            if not result.notes.startswith("КРАТКОЕ ОПИСАНИЕ:"):
                result.notes = f"КРАТКОЕ ОПИСАНИЕ:\n{result.notes}"
            
            return result
            
        except Exception as e:
            print(f"Error in summary generation: {e}")
            return ThreadSummary(
                notes="КРАТКОЕ ОПИСАНИЕ:\nОшибка при анализе письма. Требуется ручная проверка.",
                key_points=[],
                next_steps=[],
                priority="medium"
            )
    
    def process_thread(self, thread_id: str, thread_text: str, headers: Dict[str, str]) -> Dict:
        """
        Process a single email thread using LangChain.
        
        Args:
            thread_id: Gmail thread ID
            thread_text: Email thread text
            headers: Email headers
            
        Returns:
            Processing result dictionary
        """
        try:
            # Check if this is a company email
            is_company_email = self._is_company_email(thread_text, headers)
            
            if is_company_email:
                return {
                    "status": "skip",
                    "thread_id": thread_id,
                    "is_company_email": True,
                    "reason": "Company email - filtered out"
                }
            
            # Classify the thread
            classification = self.classify_thread(thread_text)
            
            if not classification.is_lead:
                return {
                    "status": "skip",
                    "thread_id": thread_id,
                    "is_company_email": False,
                    "classification": classification,
                    "reason": classification.reason
                }
            
            # Extract contact information
            contact_info = self.extract_contact(thread_text, headers)
            
            if not contact_info.email:
                return {
                    "status": "error",
                    "thread_id": thread_id,
                    "error_message": "No email address found"
                }
            
            # Generate summary
            summary = self.summarize_thread(thread_text)
            
            return {
                "status": "success",
                "thread_id": thread_id,
                "is_company_email": False,
                "classification": classification,
                "contact_info": contact_info,
                "summary": summary
            }
            
        except Exception as e:
            return {
                "status": "error",
                "thread_id": thread_id,
                "error_message": f"Processing failed: {e}"
            }

# Legacy compatibility functions
def classify_thread(thread_text: str) -> Dict[str, any]:
    """Legacy function for backward compatibility."""
    processor = LangChainLLMProcessor()
    result = processor.process_thread("legacy", thread_text, {})
    
    if result["status"] == "success" and result["classification"]:
        return {
            "is_lead": result["classification"].is_lead,
            "reason": result["classification"].reason
        }
    else:
        return {
            "is_lead": True,  # Default to lead on error
            "reason": "Error in classification - manual review recommended"
        }

def extract_contact(thread_text: str, headers: Dict[str, str] = None) -> Dict[str, str]:
    """Legacy function for backward compatibility."""
    processor = LangChainLLMProcessor()
    result = processor.process_thread("legacy", thread_text, headers or {})
    
    if result["status"] == "success" and result["contact_info"]:
        contact = result["contact_info"]
        return {
            "email": contact.email,
            "name": contact.name,
            "company": contact.company,
            "phone": contact.phone,
            "language": contact.language,
            "country": contact.country,
            "business_type": contact.business_type,
            "interest": contact.interest
        }
    else:
        return {
            "email": "", "name": "", "company": "", "phone": "",
            "language": "", "country": "", "business_type": "", "interest": ""
        }

def summarize_thread(thread_text: str) -> Dict[str, str]:
    """Legacy function for backward compatibility."""
    processor = LangChainLLMProcessor()
    result = processor.process_thread("legacy", thread_text, {})
    
    if result["status"] == "success" and result["summary"]:
        return {"notes": result["summary"].notes}
    else:
        return {"notes": "КРАТКОЕ ОПИСАНИЕ:\nОшибка при анализе письма. Требуется ручная проверка."}



