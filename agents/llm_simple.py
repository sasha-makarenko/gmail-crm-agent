"""
Simplified LLM Processor for Gmail Thread Analysis

This module provides a focused LLM processing system that extracts only
basic contact information without generating summaries.
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, Field

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
    business_relevance: str = Field(description="How relevant this is to SD Pearls business")

class SimpleLLMProcessor:
    """Simplified LLM processor focused on contact extraction."""
    
    # Company information for filtering
    COMPANY_EMAILS = ["info@sweet-sdpearls.de", "hello.sdpearls@gmail.com"]
    COMPANY_NAMES = ["SD Pearls", "Sweet SD Pearls"]
    COMPANY_PEOPLE = ["Nataliia Makarenko", "Nataliia", "Makarenko", "Наталия Макаренко", "Наталія Макаренко"]
    
    # Business context for SD Pearls
    BUSINESS_CONTEXT = """
    SD Pearls is a European manufacturer of sugar sprinkles and edible cake decorations.
    - Founder & CEO: Nataliia Makarenko
    - Business: B2B supplier for distributors, wholesalers, retail chains, HoReCa, bakeries, cake supply
    - Products: Sugar Sprinkles and edible cake decorations
    - Production: Full in-house production
    
    Typical commercial requests we handle:
    - Catalogues, price lists, quotations/RFQs
    - MOQs, lead times, availability, samples
    - Private label/white label inquiries
    - Packaging options (retail vs. bulk)
    - Seasonal assortments (Christmas, Easter, Halloween, Valentine's)
    - Quality & certificates, ingredient lists, allergen matrices
    - Distribution & partnerships, distributor onboarding
    - Orders & operations, purchase orders, order confirmations
    - Logistics & shipping, Incoterms, tracking
    - Post-delivery & returns, quality claims
    """
    
    # Spam/irrelevant patterns
    SPAM_PATTERNS = [
        "travel", "tickets", "hotel", "flight", "booking", "tourism",
        "job application", "resume", "cv", "vacancy", "work.ua", "recruitment",
        "bank", "payment", "transfer", "qonto", "financial", "accounting",
        "automated", "noreply", "no-reply", "system", "notification",
        "advertising", "promotion", "marketing", "newsletter", "spam"
    ]
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """Initialize Simple LLM processor."""
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
        
        # Create prompt templates
        self._create_prompt_templates()
    
    def _create_prompt_templates(self):
        """Create simplified prompt templates."""
        
        # Lead classification prompt
        self.classification_prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are an expert business development specialist for SD Pearls, a European manufacturer of sugar sprinkles and edible cake decorations.

{self.BUSINESS_CONTEXT}

Your task is to identify ANY potential business opportunities. Be SENSITIVE to potential leads - it's better to capture a potential lead than to miss one.

CLASSIFY AS A LEAD if the email contains ANY of the following:

🎯 **Direct Business Inquiries** (related to SD Pearls products):
- Questions about sugar sprinkles, edible decorations, cake supplies, baking ingredients
- Requests for catalogs, price lists, quotations, samples
- Inquiries about MOQs, lead times, availability, product specifications
- Private label/white label inquiries
- Packaging options (retail vs. bulk)
- Seasonal assortments (Christmas, Easter, Halloween, Valentine's)
- Quality & certificates, ingredient lists, allergen information
- Distribution & partnership discussions
- Orders & operations, purchase orders, order confirmations
- Logistics & shipping, delivery, tracking
- Customer service inquiries about our products
- Product questions or technical support requests
- Business meetings or appointment requests
- Any communication with real people about business matters
- Client feedback or testimonials
- Supplier communications (if relevant to our business)
- Any meaningful business conversation
- Questions about shipping, delivery, or availability
- Requests for catalogs, samples, or product information
- Inquiries about bulk orders or wholesale pricing
- Questions about product quality or specifications
- Any mention of "cake", "decorating", "supplies", "tools", "materials", "baking", "confectionery"
- Business inquiries in any language (German, English, Russian, Ukrainian, etc.)
- Any B2B communication that could lead to sales

❌ **ONLY REJECT** if the email is clearly:
- Travel, tickets, hotels, flights, tourism (completely unrelated to food/baking)
- Job applications, resumes, CVs, work.ua, recruitment (unless for sales roles)
- Banking, payments, transfers, qonto, financial services (unless related to our orders)
- Automated notifications, noreply, no-reply, system messages
- Pure advertising/promotions for completely unrelated products
- Internal company communications (from our own team)
- Obvious spam or irrelevant content

🏢 **Company Context**:
- Our CEO is Nataliia Makarenko (any email from her is internal)
- We sell sugar sprinkles and edible cake decorations
- We are B2B suppliers to bakeries, cafes, retail, distributors
- We don't sell travel, banking, or other services

IMPORTANT: 
- Be VERY SENSITIVE to potential business opportunities
- When in doubt, classify as A LEAD
- Focus on ANY communication that could lead to business
- Consider the broader context of food/baking industry
- Look for ANY business-related communication
- Include ANY email from a real person (not automated systems)
- Include ANY communication that mentions products, services, or business
- Include ANY inquiry, question, or request
- Include ANY follow-up or response to previous communications
- Include ANY communication that could potentially lead to a sale

{{format_instructions}}"""),
            ("user", "Analyze this email thread for business opportunities related to SD Pearls:\n\n{thread_text}")
        ])
        
        # Contact extraction prompt
        self.contact_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at extracting contact information from emails in multiple languages.

Extract ONLY relevant contact information from the email thread. Look for:

🔍 **Contact Details** (in any language):
- Email addresses (if not already found in headers)
- Names (first, last, full)
- Company names
- Phone numbers
- Addresses/countries
- Language preferences

🌍 **Language Detection**:
- Identify the primary language of the email
- Common languages: Russian, Ukrainian, German, English, etc.

💼 **Business Context**:
- What they're interested in (only if related to our business)
- Their business type (bakery, cafe, retail, etc.)
- Order size (retail, wholesale, bulk)
- Specific products mentioned

IMPORTANT: 
- Extract information in ANY language
- Be thorough - extract everything you can find
- If information is missing, use empty string
- Preserve original language when possible
- Focus on finding email addresses if they exist in the text
- Return ONLY the JSON format specified below, no additional text

{{format_instructions}}"""),
            ("user", "Extract contact information from this email:\n\n{thread_text}")
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
        
        return False
    
    def _is_spam_or_irrelevant(self, thread_text: str, headers: Dict[str, str]) -> bool:
        """Check if this is spam or irrelevant content."""
        text_lower = thread_text.lower()
        from_email = headers.get("From", "").lower()
        
        # Check for noreply emails (but be more specific)
        if any(noreply in from_email for noreply in ["noreply@", "no-reply@", "noreply.", "no-reply."]):
            return True
        
        # Only filter out obvious spam patterns, not business-related content
        obvious_spam_patterns = [
            "work.ua", "tickets.ua", "qonto.com", "pati-versand.de", 
            "kff-group.com", "eurodix.fr", "linbraze.com"
        ]
        
        if any(pattern in text_lower for pattern in obvious_spam_patterns):
            return True
        
        # Check for pure travel content (not food-related travel)
        travel_keywords = ["travel to", "hotel booking", "flight booking", "tourism", "vacation"]
        if any(keyword in text_lower for keyword in travel_keywords):
            # But allow if it mentions food/baking context
            if not any(food_word in text_lower for food_word in ["food", "restaurant", "bakery", "cafe", "cooking", "baking"]):
                return True
        
        # Check for pure job application content
        job_keywords = ["job application", "resume", "cv", "vacancy", "work.ua", "recruitment"]
        if any(keyword in text_lower for keyword in job_keywords):
            # But allow if it's about sales positions
            if not any(sales_word in text_lower for sales_word in ["sales", "business development", "marketing"]):
                return True
        
        # Check for pure banking content (not order-related)
        financial_keywords = ["bank statement", "account balance", "qonto", "financial report"]
        if any(keyword in text_lower for keyword in financial_keywords):
            # But allow if it mentions orders or payments for our products
            if not any(order_word in text_lower for order_word in ["order", "payment", "invoice", "delivery"]):
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
        """Classify the email as a lead or not."""
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
            
        except Exception as e:
            print(f"Error in lead classification: {e}")
            return LeadClassification(
                is_lead=True,  # Default to LEAD on error (be more inclusive)
                reason=f"Classification error: {e} - defaulting to lead for manual review",
                confidence=0.3,
                lead_type="unknown",
                urgency="medium",
                language="unknown",
                business_relevance="unknown"
            )
    
    def extract_contact(self, thread_text: str, headers: Dict[str, str] = None) -> ContactInfo:
        """Extract contact information."""
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
            # Try to extract basic info from headers and text
            name = ""
            if headers:
                from_field = headers.get("From", "")
                if "<" in from_field and ">" in from_field:
                    name = from_field.split("<")[0].strip().strip('"')
            
            # Try to extract email from text if not in headers
            if not extracted_email:
                import re
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                emails = re.findall(email_pattern, thread_text)
                if emails:
                    extracted_email = emails[0]
            
            return ContactInfo(
                email=extracted_email if 'extracted_email' in locals() else "",
                name=name, company="", phone="", language="", 
                country="", business_type="", interest=""
            )
    
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
            is_company_email = self._is_company_email(thread_text, headers)
            
            if is_company_email:
                return {
                    "status": "skip",
                    "thread_id": thread_id,
                    "is_company_email": True,
                    "reason": "Company email - filtered out"
                }
            
            # Check if this is spam or irrelevant
            is_spam = self._is_spam_or_irrelevant(thread_text, headers)
            
            if is_spam:
                return {
                    "status": "skip",
                    "thread_id": thread_id,
                    "is_company_email": False,
                    "reason": "Spam or irrelevant content - filtered out"
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
            
            return {
                "status": "success",
                "thread_id": thread_id,
                "is_company_email": False,
                "classification": classification,
                "contact_info": contact_info
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
    processor = SimpleLLMProcessor()
    result = processor.process_thread("legacy", thread_text, {})
    
    if result["status"] == "success" and result["classification"]:
        return {
            "is_lead": result["classification"].is_lead,
            "reason": result["classification"].reason
        }
    else:
        return {
            "is_lead": False,  # Default to NOT lead on error
            "reason": "Error in classification - manual review recommended"
        }

def extract_contact(thread_text: str, headers: Dict[str, str] = None) -> Dict[str, str]:
    """Legacy function for backward compatibility."""
    processor = SimpleLLMProcessor()
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
    """Legacy function for backward compatibility - returns empty summary."""
    return {"notes": ""}
