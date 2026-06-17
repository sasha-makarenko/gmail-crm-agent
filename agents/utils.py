"""
Utility functions for Gmail CRM Agent

This module provides utility functions for email processing,
MIME handling, and text extraction.
"""

import base64
import quopri
import re
import logging
from email.header import decode_header, make_header
from typing import Tuple, Optional, Dict

# Configure logging
def setup_logging(level: str = "INFO") -> None:
    """
    Setup logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('gmail_crm_agent.log')
        ]
    )

# Email filtering constants
SKIP_SENDERS_SUBSTR = [
    "no-reply", "noreply", "mailer-daemon", "postmaster",
    "bounce", "noreply", "donotreply", "no-reply"
]

SKIP_DOMAINS = [
    "amazon", "pinterest", "linkedin", "facebook", "instagram",
    "twitter", "youtube", "netflix", "spotify", "uber", "lyft"
]

NEWSLETTER_HINT_HEADERS = [
    "List-Unsubscribe", "List-Id", "List-Owner", "List-Post",
    "List-Help", "List-Subscribe", "List-Unsubscribe-Post"
]

def decode_maybe(s: str) -> str:
    """
    Decode email header if it's encoded.
    
    Args:
        s: String that might be encoded
        
    Returns:
        Decoded string or original if decoding fails
    """
    if not s:
        return ""
    
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s

def is_probably_newsletter(headers: dict) -> bool:
    """
    Check if email is likely a newsletter based on headers.
    
    Args:
        headers: Email headers dictionary
        
    Returns:
        True if likely a newsletter
    """
    return any(h in headers for h in NEWSLETTER_HINT_HEADERS)

def is_auto_sender(from_email: str) -> bool:
    """
    Check if email is from an automated sender.
    
    Args:
        from_email: From email address
        
    Returns:
        True if likely an automated sender
    """
    if not from_email:
        return False
    
    f = from_email.lower()
    
    # Check for skip substrings
    if any(x in f for x in SKIP_SENDERS_SUBSTR):
        return True
    
    # Check for skip domains
    if any(d in f for d in SKIP_DOMAINS):
        return True
    
    return False

def guess_plain_text(payload: dict) -> Tuple[str, str]:
    """
    Extract readable text from MIME message structure.
    
    Args:
        payload: Gmail message payload
        
    Returns:
        Tuple of (plain_text, mime_type)
    """
    def _decode(body: str, encoding: str) -> str:
        """Decode body with specified encoding."""
        if not body:
            return ""
        
        try:
            if encoding.upper() == "BASE64":
                return base64.urlsafe_b64decode(body).decode("utf-8", errors="ignore")
            elif encoding.upper() == "QUOTED-PRINTABLE":
                return quopri.decodestring(body).decode("utf-8", errors="ignore")
            else:
                return body
        except Exception:
            return body

    def _extract_from_html(html_content: str) -> str:
        """Extract plain text from HTML content."""
        if not html_content:
            return ""
        
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", html_content)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    # Check if payload has direct text content
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")
    
    if data and mime_type.startswith("text/"):
        decoded = _decode(data, body.get("encoding", "BASE64"))
        if mime_type == "text/plain":
            return decoded, "text/plain"
        elif mime_type == "text/html":
            return _extract_from_html(decoded), "text/html"

    # Process multipart messages
    parts = payload.get("parts", []) or []
    
    # First, look for text/plain
    for part in parts:
        mt = part.get("mimeType", "")
        if mt == "text/plain":
            part_body = part.get("body", {})
            part_data = part_body.get("data")
            if part_data:
                decoded = _decode(part_data, part_body.get("encoding", "BASE64"))
                return decoded, "text/plain"
    
    # Then, look for multipart content
    for part in parts:
        mt = part.get("mimeType", "")
        if mt.startswith("multipart/"):
            txt, mt_found = guess_plain_text(part)
            if txt:
                return txt, mt_found
    
    # Finally, fall back to HTML
    for part in parts:
        mt = part.get("mimeType", "")
        if mt == "text/html":
            part_body = part.get("body", {})
            part_data = part_body.get("data")
            if part_data:
                html = _decode(part_data, part_body.get("encoding", "BASE64"))
                return _extract_from_html(html), "text/html"
    
    # Last resort: check if root is HTML
    if mime_type == "text/html" and data:
        html = _decode(data, body.get("encoding", "BASE64"))
        return _extract_from_html(html), "text/html"
    
    return "", ""

def clean_email_text(text: str) -> str:
    """
    Clean and normalize email text.
    
    Args:
        text: Raw email text
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove common email artifacts
    text = re.sub(r'--\s*\n.*', '', text)  # Remove signature
    text = re.sub(r'On .* wrote:', '', text)  # Remove reply headers
    
    return text.strip()

def extract_email_from_string(text: str) -> Optional[str]:
    """
    Extract email address from string.
    
    Args:
        text: String that might contain an email
        
    Returns:
        Email address or None
    """
    if not text:
        return None
    
    # Simple email regex
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(email_pattern, text)
    
    return match.group(0) if match else None

def extract_phone_from_string(text: str) -> Optional[str]:
    """
    Extract phone number from string.
    
    Args:
        text: String that might contain a phone number
        
    Returns:
        Phone number or None
    """
    if not text:
        return None
    
    # Phone number patterns
    phone_patterns = [
        r'\+?[\d\s\-\(\)]{10,}',  # International format
        r'\(\d{3}\)\s*\d{3}-\d{4}',  # US format (555) 123-4567
        r'\d{3}-\d{3}-\d{4}',  # US format 555-123-4567
        r'\d{10}',  # 10 digits
    ]
    
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    
    return None

def validate_configuration() -> Dict[str, bool]:
    """
    Validate the current configuration and return status.
    
    Returns:
        Dictionary with validation results
    """
    import os
    from pathlib import Path
    from dotenv import load_dotenv
    
    results = {}
    
    # Check .env file
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"
    results[".env file"] = env_path.exists()
    
    # Load .env file if it exists
    if env_path.exists():
        load_dotenv(env_path)
    
    # Check credentials.json
    credentials_path = project_root / "credentials.json"
    results["credentials.json"] = credentials_path.exists()
    
    # Check token.json
    token_path = project_root / "token.json"
    results["token.json"] = token_path.exists()
    
    # Check environment variables
    required_vars = [
        "OPENAI_API_KEY",
        "GMAIL_USER", 
        "EMAIL_FILTER",
        "SHEETS_SPREADSHEET_ID",
        "SHEETS_WORKSHEET_NAME"
    ]
    
    for var in required_vars:
        results[f"ENV_{var}"] = bool(os.getenv(var))
    
    return results

def print_configuration_status():
    """Print current configuration status for troubleshooting."""
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    results = validate_configuration()
    
    table = Table(title="Configuration Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="magenta")
    
    for component, status in results.items():
        status_text = "✓ OK" if status else "✗ Missing"
        style = "green" if status else "red"
        table.add_row(component, f"[{style}]{status_text}[/{style}]")
    
    console.print(table)
    
    # Provide helpful hints
    missing = [k for k, v in results.items() if not v]
    if missing:
        console.print("\n[yellow]Missing components:[/yellow]")
        for component in missing:
            if component == ".env file":
                console.print("  - Create .env file in project root")
            elif component == "credentials.json":
                console.print("  - Download credentials.json from Google Cloud Console")
            elif component == "token.json":
                console.print("  - Run the agent once to generate token.json")
            elif component.startswith("ENV_"):
                var_name = component.replace("ENV_", "")
                console.print(f"  - Add {var_name} to your .env file")