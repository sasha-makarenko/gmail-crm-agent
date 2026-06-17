"""
Google Sheets Client

This module provides a high-level interface for Google Sheets operations
including lead management and CRM data updates.
"""

import os
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path

class SheetsClient:
    """Google Sheets client for CRM lead management."""
    
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    
    def __init__(self, spreadsheet_id: str, worksheet_name: str = "Leads"):
        """
        Initialize Sheets client.
        
        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            worksheet_name: Name of the worksheet to use
        """
        self.spreadsheet_id = spreadsheet_id
        self.worksheet_name = worksheet_name
        self.project_root = Path(__file__).resolve().parents[1]
        self.credentials_file = self.project_root / "credentials.json"
        self.token_file = self.project_root / "token.json"
        self._service = None
        self._cached_rows = None
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
        """Get or create Sheets service with authentication."""
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
        
        self._service = build("sheets", "v4", credentials=creds)
        return self._service
    
    def validate_access(self) -> bool:
        """Validate that we can access the spreadsheet and worksheet."""
        try:
            service = self._get_service()
            
            def _test_access():
                return service.spreadsheets().get(
                    spreadsheetId=self.spreadsheet_id
                ).execute()
            
            spreadsheet_info = self._retry_request(_test_access)
            worksheet_names = [sheet["properties"]["title"] for sheet in spreadsheet_info["sheets"]]
            
            if self.worksheet_name not in worksheet_names:
                print(f"Warning: Worksheet '{self.worksheet_name}' not found. Available: {worksheet_names}")
                return False
            
            return True
        except Exception as e:
            print(f"Error validating spreadsheet access: {e}")
            return False
    
    def _ensure_header_row(self):
        """Ensure the header row exists with correct column structure."""
        headers = [
            "Company", "Address", "Website", "LPR Name", "LPR Phone",
            "LPR Email", "Notes", "Source", "ThreadId",
            "FirstSeen", "LastUpdated", "Status"
        ]


        service = self._get_service()
        range_name = f"{self.worksheet_name}!A1:L1"
        
        try:
            # Check if headers exist
            result = service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, 
                range=range_name
            ).execute()
            
            existing_headers = result.get("values", [[]])[0] if result.get("values") else []
            
            if existing_headers != headers:
                # Update headers
                service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption="RAW",
                    body={"values": [headers]}
                ).execute()
        except Exception as e:
            # If worksheet doesn't exist, create it
            if "Unable to parse range" in str(e):
                # Create worksheet by writing headers
                service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption="RAW",
                    body={"values": [headers]}
                ).execute()
    
    def _get_all_rows(self) -> List[List[str]]:
        """Get all rows from the worksheet (cached)."""
        if self._cached_rows is not None:
            return self._cached_rows

        service = self._get_service()
        range_name = f"{self.worksheet_name}!A2:L"  # Skip header row
        
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, 
                range=range_name
            ).execute()
            
            self._cached_rows = result.get("values", [])
            return self._cached_rows
        except Exception:
            self._cached_rows = []
            return []
    
    def _find_row_by_email(self, email: str) -> Optional[int]:
        """
        Find row index by LPR Email (lowercased, column F / index 5).

        Args:
            email: Email address to search for

        Returns:
            Row index (1-based, including header) or None if not found
        """
        if not email:
            return None

        email_lower = email.strip().lower()
        rows = self._get_all_rows()

        for i, row in enumerate(rows, start=2):  # Start from 2 (after header)
            # LPR Email is column F (index 5)
            if row and len(row) > 5:
                row_email = row[5].strip().lower()
                if row_email == email_lower:
                    return i
        return None
    
    def upsert_lead(self, lead_data: Dict[str, Any], dry_run: bool = False) -> int:
        """
        Insert or update a lead in the spreadsheet by LPR Email (lowercased).

        New header schema:
        Company | Address | Website | LPR Name | LPR Phone | LPR Email | Notes |
        Source | ThreadId | FirstSeen | LastUpdated | Status

        Args:
            lead_data: Dictionary with lead information
                - lpr_email: Email address (required, column F)
                - company: Company name
                - address: Physical address
                - website: Website URL
                - lpr_name: Contact person name
                - lpr_phone: Phone number
                - notes: Summary/notes
                - source: Source (e.g., "Gmail")
                - thread_id: Gmail thread ID
                - status: Lead status (e.g., "New", "Contacted")
            dry_run: If True, don't actually write to sheets

        Returns:
            Row number where the lead was inserted/updated, or -1 for new inserts
        """
        self._ensure_header_row()

        lpr_email = lead_data.get("lpr_email", "").strip()
        if not lpr_email:
            raise ValueError("LPR Email is required for lead data")

        # Prepare timestamp
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Column mapping: A=Company, B=Address, C=Website, D=LPR Name, E=LPR Phone,
        # F=LPR Email, G=Notes, H=Source, I=ThreadId, J=FirstSeen, K=LastUpdated, L=Status
        row_values = [
            lead_data.get("company", ""),         # A: Company
            lead_data.get("address", ""),         # B: Address
            lead_data.get("website", ""),         # C: Website
            lead_data.get("lpr_name", ""),        # D: LPR Name
            lead_data.get("lpr_phone", ""),       # E: LPR Phone
            lpr_email,                             # F: LPR Email (lowercased for matching)
            lead_data.get("notes", ""),           # G: Notes
            lead_data.get("source", "Gmail"),     # H: Source
            lead_data.get("thread_id", ""),       # I: ThreadId
            "",                                    # J: FirstSeen (set below)
            now,                                   # K: LastUpdated
            lead_data.get("status", "New"),       # L: Status
        ]

        if dry_run:
            print(f"[DRY RUN] Would upsert lead: {lpr_email}")
            return -1

        service = self._get_service()
        row_idx = self._find_row_by_email(lpr_email)

        if row_idx:
            # Update existing row
            print(f"Updating existing lead at row {row_idx}: {lpr_email}")
            range_name = f"{self.worksheet_name}!A{row_idx}:L{row_idx}"

            # Get existing row data
            existing_row = self._get_all_rows()[row_idx - 2]  # Convert to 0-based

            # Preserve FirstSeen (column J, index 9)
            if existing_row and len(existing_row) > 9 and existing_row[9]:
                row_values[9] = existing_row[9]  # Keep existing FirstSeen
            else:
                row_values[9] = now  # Set FirstSeen if missing

            # Merge notes intelligently (column G, index 6)
            new_notes = lead_data.get("notes", "")
            if new_notes:
                if existing_row and len(existing_row) > 6 and existing_row[6]:
                    existing_notes = existing_row[6].strip()
                    # Only append if new notes are different
                    if new_notes.strip() != existing_notes:
                        # Simple deduplication: don't repeat the same content
                        row_values[6] = f"{existing_notes}\n\n[{now}] {new_notes}"
                    else:
                        row_values[6] = existing_notes
                else:
                    row_values[6] = f"[{now}] {new_notes}"

            # Update other fields only if they have values (don't overwrite with empty)
            for idx, (new_val, old_val) in enumerate(zip(row_values, existing_row)):
                # Skip Notes (6), FirstSeen (9), LastUpdated (10)
                if idx in [6, 9, 10]:
                    continue
                # If new value is empty but old value exists, keep old
                if not new_val and len(existing_row) > idx and existing_row[idx]:
                    row_values[idx] = existing_row[idx]

            self._retry_request(
                lambda: service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption="RAW",
                    body={"values": [row_values]},
                ).execute()
            )

            return row_idx
        else:
            # Insert new row
            print(f"Inserting new lead: {lpr_email}")
            row_values[9] = now  # Set FirstSeen for new leads
            range_name = f"{self.worksheet_name}!A2"

            self._retry_request(
                lambda: service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [row_values]},
                ).execute()
            )

            # Invalidate cache since we added a row
            self._cached_rows = None

            return -1  # New insert, row number not yet known

# Legacy functions for backward compatibility
def sheets_service(creds: Credentials):
    """Legacy function - use SheetsClient class instead."""
    return build("sheets", "v4", credentials=creds)

def get_credentials() -> Credentials:
    """Legacy function - use SheetsClient class instead."""
    from .gmail_client import GmailClient
    client = GmailClient("me")
    return client._get_service()._credentials

def ensure_header_row(svc):
    """Legacy function - use SheetsClient class instead."""
    client = SheetsClient("dummy_id")
    client._ensure_header_row()

def find_row_by_email(svc, email: str) -> Optional[int]:
    """Legacy function - use SheetsClient class instead."""
    client = SheetsClient("dummy_id")
    return client._find_row_by_email(email)

def upsert_lead(svc, lead: Dict[str, Any]) -> int:
    """Legacy function - use SheetsClient class instead."""
    client = SheetsClient("dummy_id")
    return client.upsert_lead(lead)