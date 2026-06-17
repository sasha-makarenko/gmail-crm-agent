"""
Debug script to analyze a single email thread and understand classification logic.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from .gmail_client import GmailClient
from .llm import LLMProcessor

console = Console()

def load_config() -> dict:
    """Load configuration from .env file."""
    project_root = Path(__file__).parent.parent
    env_path = project_root / ".env"
    load_dotenv(env_path)
    
    return {
        "GMAIL_USER": os.getenv("GMAIL_USER"),
        "GOOGLE_TOKEN_PATH": os.getenv("GOOGLE_TOKEN_PATH", "token.json")
    }

def analyze_single_thread(thread_id: str):
    """Analyze a single thread in detail."""
    config = load_config()
    
    gmail_client = GmailClient(config["GMAIL_USER"], config["GOOGLE_TOKEN_PATH"])
    llm_processor = LLMProcessor()
    
    console.print(f"[bold blue]Analyzing thread: {thread_id}[/bold blue]")
    console.print("=" * 60)
    
    # Fetch thread
    thread = gmail_client.fetch_thread(thread_id)
    if not thread:
        console.print("[red]Failed to fetch thread[/red]")
        return
    
    # Convert to text
    thread_text, headers = gmail_client.thread_to_text_and_headers(thread)
    
    # Show headers
    console.print("[bold]Headers:[/bold]")
    for key, value in headers.items():
        if key in ["From", "To", "Subject", "Date"]:
            console.print(f"  {key}: {value}")
    
    # Show thread text (first 500 chars)
    console.print(f"\n[bold]Thread text (first 500 chars):[/bold]")
    preview = thread_text[:500] + "..." if len(thread_text) > 500 else thread_text
    console.print(Panel(preview, title="Thread Preview"))
    
    # Classify
    console.print("\n[bold]Classification:[/bold]")
    classification = llm_processor.classify_thread(thread_text)
    console.print(f"  is_lead: {classification['is_lead']}")
    console.print(f"  reason: {classification['reason']}")
    
    # Extract contact info
    console.print("\n[bold]Contact Information:[/bold]")
    contact_info = llm_processor.extract_contact(thread_text)
    for key, value in contact_info.items():
        console.print(f"  {key}: {value}")
    
    # Generate summary
    console.print("\n[bold]Summary:[/bold]")
    summary = llm_processor.summarize_thread(thread_text)
    console.print(Panel(summary['notes'], title="Business Summary"))

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        console.print("[red]Usage: python -m agents.debug <thread_id>[/red]")
        console.print("[yellow]Example: python -m agents.debug 18c1234567890abcdef[/yellow]")
        return
    
    thread_id = sys.argv[1]
    analyze_single_thread(thread_id)

if __name__ == "__main__":
    main()
