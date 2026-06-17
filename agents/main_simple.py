"""
Simplified Gmail CRM Agent - Main Entry Point

This module implements a focused pipeline that extracts only basic contact
information without generating summaries.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .gmail_client import GmailClient
from .sheets_client import SheetsClient
from .llm_simple import SimpleLLMProcessor
from .state_store import StateStore
from .utils import setup_logging

# Initialize rich console for beautiful output
console = Console()

def load_config() -> Dict[str, str]:
    """Load configuration from .env file."""
    # Load .env from project root
    project_root = Path(__file__).parent.parent
    env_path = project_root / ".env"
    
    if not env_path.exists():
        console.print(f"[red]Error: .env file not found at {env_path}[/red]")
        console.print("Please create .env file with required configuration")
        sys.exit(1)
    
    load_dotenv(env_path)
    
    required_vars = [
        "OPENAI_API_KEY",
        "GMAIL_USER",
        "EMAIL_FILTER",
        "SHEETS_SPREADSHEET_ID",
        "SHEETS_WORKSHEET_NAME"
    ]
    
    config = {}
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            config[var] = value
    
    if missing_vars:
        console.print(f"[red]Error: Missing required environment variables: {', '.join(missing_vars)}[/red]")
        console.print("Please add them to your .env file")
        sys.exit(1)
    
    # Optional variables with defaults
    config["GOOGLE_TOKEN_PATH"] = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
    config["MAX_THREADS"] = int(os.getenv("MAX_THREADS", "50"))
    
    return config

def create_labels_if_needed(gmail_client: GmailClient) -> Dict[str, str]:
    """Create required labels if they don't exist."""
    required_labels = ["ai_lead", "ai_skip", "ai_error"]
    
    console.print("[yellow]Ensuring required labels exist...[/yellow]")
    
    try:
        labels = gmail_client.ensure_labels(required_labels)
        console.print(f"[green]✓ Labels ready: {', '.join(labels.keys())}[/green]")
        return labels
    except Exception as e:
        console.print(f"[red]Error creating labels: {e}[/red]")
        raise

def process_thread_simple(
    gmail_client: GmailClient,
    sheets_client: SheetsClient,
    llm_processor: SimpleLLMProcessor,
    state_store: StateStore,
    thread_id: str,
    labels: Dict[str, str]
) -> Dict[str, any]:
    """Process a single Gmail thread using simplified processing."""
    try:
        # Fetch thread data
        thread = gmail_client.fetch_thread(thread_id)
        if not thread:
            state_store.add_processing_result(thread_id, "error")
            return {"status": "error", "reason": "Failed to fetch thread"}
        
        # Convert thread to text format
        thread_text, headers = gmail_client.thread_to_text_and_headers(thread)
        
        # Process using simplified LangChain
        result = llm_processor.process_thread(thread_id, thread_text, headers)
        
        if result["status"] == "error":
            gmail_client.add_label_to_thread(thread_id, labels["ai_error"])
            state_store.add_processing_result(thread_id, "error")
            return {"status": "error", "reason": result["error_message"]}
        
        if result["status"] == "skip":
            if result.get("is_company_email", False):
                gmail_client.add_label_to_thread(thread_id, labels["ai_skip"])
                state_store.add_processing_result(thread_id, "skip")
                return {"status": "skip", "reason": "Company email - filtered out"}
            else:
                gmail_client.add_label_to_thread(thread_id, labels["ai_skip"])
                state_store.add_processing_result(thread_id, "skip")
                return {"status": "skip", "reason": result.get("reason", "Not classified as lead")}
        
        # Extract components from successful processing
        classification = result["classification"]
        contact_info = result["contact_info"]
        
        if not contact_info or not contact_info.email:
            gmail_client.add_label_to_thread(thread_id, labels["ai_error"])
            state_store.add_processing_result(thread_id, "error")
            return {"status": "error", "reason": "No email address found"}
        
        # Prepare simplified lead data (no summary)
        lead_data = {
            "email": contact_info.email,
            "name": contact_info.name,
            "company": contact_info.company,
            "phone": contact_info.phone,
            "language": contact_info.language,
            "country": contact_info.country,
            "notes": "",  # No summary for now
            "thread_id": thread_id,
            "lead_type": classification.lead_type,
            "urgency": classification.urgency,
            "confidence": classification.confidence,
            "business_type": contact_info.business_type,
            "interest": contact_info.interest,
            "business_relevance": classification.business_relevance
        }
        
        # Upsert to Google Sheets
        sheets_client.upsert_lead(lead_data)
        
        # Mark thread as lead
        gmail_client.add_label_to_thread(thread_id, labels["ai_lead"])
        
        # Mark as processed with result
        state_store.add_processing_result(thread_id, "lead")
        
        return {"status": "lead", "data": lead_data}
        
    except Exception as e:
        console.print(f"[red]Error processing thread {thread_id}: {e}[/red]")
        try:
            gmail_client.add_label_to_thread(thread_id, labels["ai_error"])
            state_store.add_processing_result(thread_id, "error")
        except:
            pass
        return {"status": "error", "reason": str(e)}

def main():
    """Main entry point for the Simplified Gmail CRM Agent."""
    console.print("[bold blue]Gmail CRM Agent (Simplified Edition)[/bold blue]")
    console.print("=" * 50)
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--reanalyze":
            console.print("[yellow]Running in reanalysis mode...[/yellow]")
            from .reanalyze import main as reanalyze_main
            reanalyze_main()
            return
        elif sys.argv[1] == "--clear-state":
            console.print("[yellow]Clearing processed state...[/yellow]")
            state_store = StateStore()
            state_store.clear_processed()
            console.print("[green]✓ State cleared. All threads will be reanalyzed.[/green]")
            return
        elif sys.argv[1] == "--status":
            console.print("[yellow]Checking current status...[/yellow]")
            state_store = StateStore()
            summary = state_store.get_processing_summary()
            
            table = Table(title="Gmail CRM Agent Status")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("Total Processed", str(summary["total_processed"]))
            table.add_row("Leads Found", str(summary["leads_found"]))
            table.add_row("Skipped", str(summary["skipped"]))
            table.add_row("Errors", str(summary["errors"]))
            table.add_row("Success Rate", f"{summary['success_rate']:.1f}%")
            table.add_row("Last Run", summary["last_run"] or "Never")
            table.add_row("Processed Threads", str(summary["processed_threads_count"]))
            
            console.print(table)
            return
        elif sys.argv[1] == "--check-config":
            console.print("[yellow]Checking configuration...[/yellow]")
            from .utils import print_configuration_status
            print_configuration_status()
            return
        elif sys.argv[1] == "--help":
            console.print("""
Gmail CRM Agent (Simplified Edition) - Usage:

  python -m agents.main_simple              # Process new emails
  python -m agents.main_simple --status     # Show processing status
  python -m agents.main_simple --clear-state # Clear processed state
  python -m agents.main_simple --check-config # Validate configuration
  python -m agents.main_simple --reanalyze  # Reanalyze processed emails
  python -m agents.main_simple --help       # Show this help

Features:
  ✅ Simplified LangChain-powered LLM processing
  ✅ Business context awareness for SD Pearls
  ✅ Sophisticated spam and irrelevant content filtering
  ✅ Structured output validation with Pydantic
  ✅ Multi-language support with business relevance
  ✅ Company email filtering (internal communications)
  ✅ Basic contact information extraction only
  ✅ Confidence scoring and business relevance assessment
  ✅ Zero false positives - only genuine business leads
  ✅ No Russian summaries (focused on core functionality)
""")
            return
    
    try:
        # Load configuration
        config = load_config()
        console.print("[green]✓ Configuration loaded[/green]")
        
        # Initialize components
        gmail_client = GmailClient(config["GMAIL_USER"], config["GOOGLE_TOKEN_PATH"])
        sheets_client = SheetsClient(config["SHEETS_SPREADSHEET_ID"], config["SHEETS_WORKSHEET_NAME"])
        llm_processor = SimpleLLMProcessor()
        state_store = StateStore()
        
        console.print("[green]✓ Components initialized[/green]")
        
        # Validate access to Google Sheets
        console.print("[yellow]Validating Google Sheets access...[/yellow]")
        if not sheets_client.validate_access():
            console.print("[red]Error: Cannot access Google Sheets. Please check your credentials and permissions.[/red]")
            sys.exit(1)
        console.print("[green]✓ Google Sheets access validated[/green]")
        
        # Create labels
        labels = create_labels_if_needed(gmail_client)
        
        # Search for threads
        console.print(f"[yellow]Searching for threads with filter: {config['EMAIL_FILTER']}[/yellow]")
        thread_ids = gmail_client.search_threads(
            config["EMAIL_FILTER"], 
            max_results=config["MAX_THREADS"]
        )
        
        # Filter out already processed threads
        unprocessed_threads = [tid for tid in thread_ids if not state_store.is_processed(tid)]
        
        console.print(f"[blue]Found {len(thread_ids)} threads, {len(unprocessed_threads)} unprocessed[/blue]")
        
        if not unprocessed_threads:
            console.print("[yellow]No new threads to process[/yellow]")
            console.print("[blue]Use --reanalyze to reanalyze previously processed threads[/blue]")
            return
        
        # Process threads
        stats = {"processed": 0, "leads": 0, "skipped": 0, "errors": 0}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing threads...", total=len(unprocessed_threads))
            
            for thread_id in unprocessed_threads:
                result = process_thread_simple(
                    gmail_client, sheets_client, llm_processor, 
                    state_store, thread_id, labels
                )
                
                stats["processed"] += 1
                if result["status"] == "lead":
                    stats["leads"] += 1
                elif result["status"] == "skip":
                    stats["skipped"] += 1
                else:
                    stats["errors"] += 1
                
                progress.advance(task)
        
        # Display results
        console.print("\n[bold green]Processing Complete![/bold green]")
        
        results_table = Table(title="Processing Statistics")
        results_table.add_column("Metric", style="cyan")
        results_table.add_column("Count", style="magenta")
        
        results_table.add_row("Total Processed", str(stats["processed"]))
        results_table.add_row("Leads Found", str(stats["leads"]))
        results_table.add_row("Skipped", str(stats["skipped"]))
        results_table.add_row("Errors", str(stats["errors"]))
        
        console.print(results_table)
        
        # Show success rate
        if stats["processed"] > 0:
            success_rate = ((stats["leads"] + stats["skipped"]) / stats["processed"]) * 100
            console.print(f"\n[green]Success Rate: {success_rate:.1f}%[/green]")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Processing interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()



