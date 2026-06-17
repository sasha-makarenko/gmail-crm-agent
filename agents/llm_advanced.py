"""
Advanced Context-Aware LLM Processor for Gmail Thread Analysis

This module provides a sophisticated, business-context-aware LLM processing system
using LangChain with memory, advanced filtering, and domain-specific knowledge.
"""

import os
import json
from typing import Dict, List, Optional, TypedDict, Annotated
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage
# Memory functionality will be added later
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
    business_relevance: str = Field(description="How relevant this is to SD Pearls business")

class ThreadSummary(BaseModel):
    """Thread summary result."""
    notes: str = Field(description="Concise summary in Russian (3-4 sentences)")
    key_points: List[str] = Field(description="Key business points")
    next_steps: List[str] = Field(description="Recommended next steps")
    priority: str = Field(description="Priority level (low, medium, high)")

class AdvancedLLMProcessor:
    """Advanced LLM processor with business context awareness."""
    
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
        """Initialize Advanced LLM processor."""
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
        
        # Memory functionality will be added later
        # self.memory = ConversationBufferMemory(...)
        
        # Initialize output parsers
        self.classification_parser = PydanticOutputParser(pydantic_object=LeadClassification)
        self.contact_parser = PydanticOutputParser(pydantic_object=ContactInfo)
        self.summary_parser = PydanticOutputParser(pydantic_object=ThreadSummary)
        
        # Create prompt templates
        self._create_prompt_templates()
    
    def _create_prompt_templates(self):
        """Create advanced prompt templates with business context."""
        
        # Advanced lead classification prompt
        self.classification_prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are an expert business development specialist for SD Pearls, a European manufacturer of sugar sprinkles and edible cake decorations.

{self.BUSINESS_CONTEXT}

Your task is to identify ONLY genuine business opportunities related to SD Pearls' products and services. Be VERY STRICT and precise - it's better to miss a potential lead than to create false positives.

CLASSIFY AS A LEAD ONLY if the email contains:

🎯 **Direct Business Inquiries** (related to SD Pearls products):
- Questions about sugar sprinkles, edible decorations, cake supplies
- Requests for catalogs, price lists, quotations for our products
- Inquiries about MOQs, lead times, availability, samples
- Private label/white label inquiries for our products
- Packaging options (retail vs. bulk) for our products
- Seasonal assortments (Christmas, Easter, Halloween) for our products
- Quality & certificates for our products
- Distribution & partnership discussions for our products
- Orders & operations for our products
- Logistics & shipping for our products

❌ **NEVER CLASSIFY AS LEAD** if the email contains:
- Travel, tickets, hotels, flights, tourism (completely unrelated)
- Job applications, resumes, CVs, work.ua, recruitment (not customers)
- Banking, payments, transfers, qonto, financial services (not customers)
- Automated notifications, noreply, no-reply, system messages
- Advertising, promotions, marketing for other companies
- Internal company communications (from our own team)
- Spam or irrelevant content

🏢 **Company Context**:
- Our CEO is Nataliia Makarenko (any email from her is internal)
- We only sell sugar sprinkles and edible cake decorations
- We are B2B suppliers, not B2C
- We don't sell travel, banking, or other services

IMPORTANT: 
- Be EXTREMELY STRICT about relevance to our business
- When in doubt, classify as NOT A LEAD
- Focus only on genuine business opportunities for our products
- Ignore all unrelated services, spam, and internal communications

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

{{format_instructions}}"""),
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
- What the customer wants/needs (only if related to our business)
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

{{format_instructions}}"""),
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
        
        return False
    
    def _is_spam_or_irrelevant(self, thread_text: str, headers: Dict[str, str]) -> bool:
        """Check if this is spam or irrelevant content."""
        text_lower = thread_text.lower()
        from_email = headers.get("From", "").lower()
        
        # Check for spam patterns
        if any(pattern in text_lower for pattern in self.SPAM_PATTERNS):
            return True
        
        # Check for noreply emails
        if any(noreply in from_email for noreply in ["noreply", "no-reply", "noreply@", "no-reply@"]):
            return True
        
        # Check for travel-related content
        travel_keywords = ["travel", "tickets", "hotel", "flight", "booking", "tourism", "trip", "journey"]
        if any(keyword in text_lower for keyword in travel_keywords):
            return True
        
        # Check for job application content
        job_keywords = ["job", "resume", "cv", "vacancy", "work.ua", "recruitment", "position", "application"]
        if any(keyword in text_lower for keyword in job_keywords):
            return True
        
        # Check for banking/financial content
        financial_keywords = ["bank", "payment", "transfer", "qonto", "financial", "accounting", "money", "euro", "€"]
        if any(keyword in text_lower for keyword in financial_keywords):
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
        """Classify the email as a lead or not using advanced context awareness."""
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
                is_lead=False,  # Default to NOT lead on parsing error
                reason="Classification parsing error - manual review recommended",
                confidence=0.3,
                lead_type="unknown",
                urgency="low",
                language="unknown",
                business_relevance="unknown"
            )
        except Exception as e:
            print(f"Error in lead classification: {e}")
            return LeadClassification(
                is_lead=False,  # Default to NOT lead on error
                reason=f"Classification error: {e} - manual review recommended",
                confidence=0.2,
                lead_type="unknown",
                urgency="low",
                language="unknown",
                business_relevance="unknown"
            )
    
    def extract_contact(self, thread_text: str, headers: Dict[str, str] = None) -> ContactInfo:
        """Extract contact information using advanced context awareness."""
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
            # Try to extract basic info from headers
            name = ""
            if headers:
                from_field = headers.get("From", "")
                if "<" in from_field and ">" in from_field:
                    name = from_field.split("<")[0].strip().strip('"')
            
            return ContactInfo(
                email=extracted_email if 'extracted_email' in locals() else "",
                name=name, company="", phone="", language="", 
                country="", business_type="", interest=""
            )
    
    def summarize_thread(self, thread_text: str) -> ThreadSummary:
        """Generate Russian summary using advanced context awareness."""
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
            # Create a basic summary from the thread text
            basic_summary = f"КРАТКОЕ ОПИСАНИЕ:\nКлиент отправил сообщение. Требуется ручная проверка для определения деталей."
            return ThreadSummary(
                notes=basic_summary,
                key_points=["Требуется ручная проверка"],
                next_steps=["Связаться с клиентом"],
                priority="medium"
            )
    
    def process_thread(self, thread_id: str, thread_text: str, headers: Dict[str, str]) -> Dict:
        """
        Process a single email thread using advanced context awareness.
        
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
    processor = AdvancedLLMProcessor()
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
    processor = AdvancedLLMProcessor()
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
    processor = AdvancedLLMProcessor()
    result = processor.process_thread("legacy", thread_text, {})
    
    if result["status"] == "success" and result["summary"]:
        return {"notes": result["summary"].notes}
    else:
        return {"notes": "КРАТКОЕ ОПИСАНИЕ:\nОшибка при анализе письма. Требуется ручная проверка."}
