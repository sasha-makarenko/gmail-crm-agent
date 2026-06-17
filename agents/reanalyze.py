"""
Reanalyze processed email threads with improved classification logic.

This script allows reanalysis of previously processed threads that were
incorrectly classified as spam.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .gmail_client import GmailClient
from .sheets_client import SheetsClient
from .llm import LLMProcessor
from .state_store import StateStore
from .utils import setup_logging

console = Console()

def load_config() -> Dict[str, str]:
    """Load configuration from .env file."""
    project_root = Path(__file__).parent.parent
    env_path = project_root / ".env"
    
    if not env_path.exists():
        console.print(f"[red]Error: .env file not found at {env_path}[/red]")
        sys.exit(1)
    
    load_dotenv(env_path)
    
    config = {}
    required_vars = [
        "OPENAI_API_KEY", "GMAIL_USER", "EMAIL_FILTER", 
        "SHEETS_SPREADSHEET_ID", "SHEETS_WORKSHEET_NAME"
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            console.print(f"[red]Error: Missing {var} in .env file[/red]")
            sys.exit(1)
        config[var] = value
    
    config["GOOGLE_TOKEN_PATH"] = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
    return config

def reanalyze_thread(
    gmail_client: GmailClient,
    sheets_client: SheetsClient,
    llm_processor: LLMProcessor,
    thread_id: str,
    labels: Dict[str, str]
) -> Dict[str, Any]:
    """Reanalyze a single thread with improved logic."""
    try:
        # Fetch thread data
        thread = gmail_client.fetch_thread(thread_id)
        if not thread:
            return {"status": "error", "reason": "Failed to fetch thread"}
        
        # Convert thread to text format
        thread_text, headers = gmail_client.thread_to_text_and_headers(thread)
        
        # Classify thread with improved logic
        classification = llm_processor.classify_thread(thread_text)
        
        if not classification["is_lead"]:
            return {"status": "skip", "reason": classification["reason"]}
        
        # Extract contact information
        contact_info = llm_processor.extract_contact(thread_text)
        
        # Generate comprehensive summary
        summary = llm_processor.summarize_thread(thread_text)
        
        # Prepare lead data
        lead_data = {
            "email": contact_info.get("email"),
            "name": contact_info.get("name"),
            "company": contact_info.get("company"),
            "phone": contact_info.get("phone"),
            "language": contact_info.get("language"),
            "country": contact_info.get("country"),
            "notes": summary.get("notes", ""),
            "thread_id": thread_id
        }
        
        # Upsert to Google Sheets
        sheets_client.upsert_lead(lead_data)
        
        # Update label from ai_skip to ai_lead
        try:
            gmail_client.add_label_to_thread(thread_id, labels["ai_lead"])
            # Remove ai_skip label if it exists
            # Note: Gmail API doesn't have direct remove label, but we can modify the thread
        except Exception as e:
            console.print(f"[yellow]Warning: Could not update labels for {thread_id}: {e}[/yellow]")
        
        return {"status": "lead", "data": lead_data}
        
    except Exception as e:
        console.print(f"[red]Error reanalyzing thread {thread_id}: {e}[/red]")
        return {"status": "error", "reason": str(e)}

def main():
    """Main entry point for reanalysis."""
    console.print("[bold blue]Gmail CRM Agent - Reanalysis Tool[/bold blue]")
    console.print("=" * 60)
    
    try:
        # Load configuration
        config = load_config()
        console.print("[green]✓ Configuration loaded[/green]")
        
        # Initialize components
        gmail_client = GmailClient(config["GMAIL_USER"], config["GOOGLE_TOKEN_PATH"])
        sheets_client = SheetsClient(config["SHEETS_SPREADSHEET_ID"], config["SHEETS_WORKSHEET_NAME"])
        llm_processor = LLMProcessor()
        state_store = StateStore()
        
        console.print("[green]✓ Components initialized[/green]")
        
        # Get labels
        labels = gmail_client.ensure_labels(["ai_lead", "ai_skip", "ai_error"])
        console.print(f"[green]✓ Labels ready: {', '.join(labels.keys())}[/green]")
        
        # Get processed threads
        processed_threads = state_store.get_processed_threads()
        console.print(f"[blue]Found {len(processed_threads)} processed threads[/blue]")
        
        if not processed_threads:
            console.print("[yellow]No processed threads found[/yellow]")
            return
        
        # Reanalyze threads
        stats = {"processed": 0, "leads": 0, "skipped": 0, "errors": 0}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Reanalyzing threads...", total=len(processed_threads))
            
            for thread_id in processed_threads:
                result = reanalyze_thread(
                    gmail_client, sheets_client, llm_processor, 
                    thread_id, labels
                )
                
                stats["processed"] += 1
                if result["status"] == "lead":
                    stats["leads"] += 1
                    console.print(f"[green]✓ Found lead: {thread_id}[/green]")
                elif result["status"] == "skip":
                    stats["skipped"] += 1
                elif result["status"] == "error":
                    stats["errors"] += 1
                
                progress.advance(task)
        
        # Display results
        console.print("\n[bold green]Reanalysis Complete![/bold green]")
        
        table = Table(title="Reanalysis Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="magenta")
        
        table.add_row("Total Reanalyzed", str(stats["processed"]))
        table.add_row("New Leads Found", str(stats["leads"]))
        table.add_row("Still Skipped", str(stats["skipped"]))
        table.add_row("Errors", str(stats["errors"]))
        
        console.print(table)
        
        if stats["leads"] > 0:
            console.print(f"\n[green]Successfully found {stats['leads']} new leads![/green]")
            console.print("Check your Google Sheets for updated information.")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Process interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
