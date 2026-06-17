"""
Gmail API Client

This module provides a high-level interface for Gmail API operations
including authentication, thread management, and label operations.
"""

import time
from pathlib import Path
import os
from typing import Dict, List, Tuple, Optional, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .utils import decode_maybe, guess_plain_text
import html2text

class GmailClient:
    """Gmail API client for thread processing and label management."""
    
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    
    def __init__(self, user_email: str, token_path: str = "token.json"):
        """
        Initialize Gmail client.
        
        Args:
            user_email: Gmail user email address
            token_path: Path to OAuth token file
        """
        self.user_email = user_email
        self.project_root = Path(__file__).resolve().parents[1]
        self.credentials_file = self.project_root / "credentials.json"
        self.token_file = self.project_root / token_path
        self._service = None
        self._last_request_time = 0
        self._min_request_interval = 0.1  # 100ms between requests
    
    def _rate_limit(self):
        """Implement basic rate limiting for API calls."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            time.sleep(self._min_request_interval - time_since_last)
        self._last_request_time = time.time()
    
    def _retry_request(self, func, max_retries: int = 3, delay: float = 1.0):
        """Retry a function with exponential backoff."""
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                return func()
            except HttpError as e:
                if e.resp.status in [429, 500, 502, 503, 504]:  # Rate limit or server errors
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                raise
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = delay * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                raise
        return func()  # Last attempt
    
    def _get_service(self):
        """Get or create Gmail service with authentication."""
        if self._service is not None:
            return self._service
        
        creds = None
        if self.token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
            except Exception as e:
                print(f"Warning: Could not load existing token: {e}")
                # Remove corrupted token file
                self.token_file.unlink(missing_ok=True)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Warning: Could not refresh token: {e}")
                    # Remove expired token file
                    self.token_file.unlink(missing_ok=True)
                    creds = None
            
            if not creds:
                if not self.credentials_file.exists():
                    raise FileNotFoundError(
                        f"credentials.json not found at {self.credentials_file}. "
                        "Please download it from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_file), self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save token
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_file, "w") as token:
                token.write(creds.to_json())
        
        self._service = build("gmail", "v1", credentials=creds)
        return self._service
    
    def ensure_labels(self, desired_labels: List[str]) -> Dict[str, str]:
        """
        Create labels if they don't exist and return {name: id} mapping.
        
        Args:
            desired_labels: List of label names to ensure exist
            
        Returns:
            Dictionary mapping label names to their IDs
        """
        service = self._get_service()
        
        def _list_labels():
            return service.users().labels().list(userId="me").execute()
        
        def _create_label(name):
            return service.users().labels().create(
                userId="me", 
                body={"name": name}
            ).execute()
        
        res = self._retry_request(_list_labels)
        labels = res.get("labels", [])
        by_name = {l["name"]: l["id"] for l in labels}
        
        out = {}
        for name in desired_labels:
            if name in by_name:
                out[name] = by_name[name]
            else:
                created = self._retry_request(lambda: _create_label(name))
                out[name] = created["id"]
        
        return out
    
    def search_threads(self, query: str, max_results: int = 20) -> List[str]:
        """
        Search for Gmail threads matching the query.
        
        Args:
            query: Gmail search query
            max_results: Maximum number of threads to return
            
        Returns:
            List of thread IDs
        """
        service = self._get_service()
        
        def _search():
            return service.users().threads().list(
                userId="me", 
                q=query, 
                maxResults=max_results
            ).execute()
        
        res = self._retry_request(_search)
        return [t["id"] for t in res.get("threads", [])]
    
    def fetch_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full thread data by ID.
        
        Args:
            thread_id: Gmail thread ID
            
        Returns:
            Thread data or None if not found
        """
        try:
            service = self._get_service()
            
            def _fetch():
                return service.users().threads().get(
                    userId="me", 
                    id=thread_id, 
                    format="full"
                ).execute()
            
            return self._retry_request(_fetch)
        except Exception as e:
            print(f"Error fetching thread {thread_id}: {e}")
            return None
    
    def thread_to_text_and_headers(self, thread: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
        """
        Convert thread to plain text and extract headers.
        Uses html2text for better HTML to plain text conversion.

        Args:
            thread: Gmail thread data

        Returns:
            Tuple of (full_text, headers_dict)
        """
        msgs = thread.get("messages", [])
        headers_all: Dict[str, str] = {}
        parts_text: List[str] = []

        # Initialize html2text converter
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_emphasis = False
        h.body_width = 0  # Don't wrap lines

        for m in msgs:
            payload = m.get("payload", {}) or {}
            headers = payload.get("headers", []) or []

            # Build headers dict for this message
            hdict = {
                h_item.get("name", ""): h_item.get("value", "")
                for h_item in headers
                if "name" in h_item and "value" in h_item
            }

            # Merge into thread-level headers without overwriting existing values
            for k, v in hdict.items():
                if v and not headers_all.get(k):
                    headers_all[k] = v

            # Extract plain text from payload
            plain_text, mime_type = guess_plain_text(payload)

            # If we got HTML, convert it with html2text for better quality
            if plain_text and mime_type == "text/html":
                try:
                    plain_text = h.handle(plain_text)
                except Exception as e:
                    # Fallback to the already extracted text if html2text fails
                    print(f"Warning: html2text failed, using fallback: {e}")

            if plain_text:
                parts_text.append(plain_text)

        full_text = "\n\n---\n\n".join(parts_text)
        # Ensure we have valid text content
        if not full_text or full_text.isspace():
            full_text = "No text content available"
        return full_text.strip(), headers_all
    
    def add_label_to_thread(self, thread_id: str, label_id: str):
        """
        Add a label to a thread.
        
        Args:
            thread_id: Gmail thread ID
            label_id: Gmail label ID
        """
        service = self._get_service()
        
        def _modify():
            return service.users().threads().modify(
                userId="me",
                id=thread_id,
                body={"addLabelIds": [label_id], "removeLabelIds": []},
            ).execute()
        
        self._retry_request(_modify)

# Legacy functions for backward compatibility
def gmail_service():
    """Legacy function - use GmailClient class instead."""
    client = GmailClient("me")
    return client._get_service()

def ensure_labels(svc, desired: List[str]) -> Dict[str, str]:
    """Legacy function - use GmailClient class instead."""
    client = GmailClient("me")
    return client.ensure_labels(desired)

def search_threads(svc, q: str, max_results: int = 20) -> List[str]:
    """Legacy function - use GmailClient class instead."""
    client = GmailClient("me")
    return client.search_threads(q, max_results)

def fetch_thread(svc, thread_id: str):
    """Legacy function - use GmailClient class instead."""
    client = GmailClient("me")
    return client.fetch_thread(thread_id)

def thread_to_text_and_headers(thread) -> Tuple[str, Dict[str, str], str, List[str]]:
    """Legacy function - use GmailClient class instead."""
    client = GmailClient("me")
    full_text, headers = client.thread_to_text_and_headers(thread)
    subject = decode_maybe(headers.get("Subject", "") or "")
    msg_ids = [m.get("id", "") for m in thread.get("messages", [])]
    return full_text, headers, subject, msg_ids

def add_label_to_thread(svc, thread_id: str, label_id: str):
    """Legacy function - use GmailClient class instead."""
    client = GmailClient("me")
    client.add_label_to_thread(thread_id, label_id)