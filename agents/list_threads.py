"""
List available email threads for analysis.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from .gmail_client import GmailClient

console = Console()

def load_config() -> dict:
    """Load configuration from .env file."""
    project_root = Path(__file__).parent.parent
    env_path = project_root / ".env"
    load_dotenv(env_path)
    
    return {
        "GMAIL_USER": os.getenv("GMAIL_USER"),
        "EMAIL_FILTER": os.getenv("EMAIL_FILTER"),
        "GOOGLE_TOKEN_PATH": os.getenv("GOOGLE_TOKEN_PATH", "token.json")
    }

def list_threads(max_results: int = 10):
    """List available threads."""
    config = load_config()
    
    gmail_client = GmailClient(config["GMAIL_USER"], config["GOOGLE_TOKEN_PATH"])
    
    console.print(f"[bold blue]Listing threads with filter: {config['EMAIL_FILTER']}[/bold blue]")
    console.print("=" * 60)
    
    # Get thread IDs
    thread_ids = gmail_client.search_threads(config["EMAIL_FILTER"], max_results=max_results)
    
    if not thread_ids:
        console.print("[yellow]No threads found[/yellow]")
        return
    
    # Create table
    table = Table(title=f"Found {len(thread_ids)} threads")
    table.add_column("Index", style="cyan")
    table.add_column("Thread ID", style="green")
    table.add_column("Subject", style="yellow")
    table.add_column("From", style="magenta")
    
    # Fetch basic info for each thread
    for i, thread_id in enumerate(thread_ids, 1):
        try:
            thread = gmail_client.fetch_thread(thread_id)
            if thread and thread.get("messages"):
                # Get first message headers
                first_msg = thread["messages"][0]
                payload = first_msg.get("payload", {})
                headers = payload.get("headers", [])
                
                subject = "No subject"
                from_header = "Unknown"
                
                for header in headers:
                    if header.get("name") == "Subject":
                        subject = header.get("value", "No subject")
                    elif header.get("name") == "From":
                        from_header = header.get("value", "Unknown")
                
                table.add_row(str(i), thread_id, subject[:50], from_header[:50])
            else:
                table.add_row(str(i), thread_id, "Error fetching", "Error")
        except Exception as e:
            table.add_row(str(i), thread_id, f"Error: {str(e)[:30]}", "Error")
    
    console.print(table)
    console.print(f"\n[blue]To analyze a specific thread, use:[/blue]")
    console.print(f"[green]python -m agents.debug <thread_id>[/green]")

def main():
    """Main entry point."""
    max_results = 10
    if len(sys.argv) > 1:
        try:
            max_results = int(sys.argv[1])
        except ValueError:
            console.print("[red]Invalid number. Using default of 10.[/red]")
    
    list_threads(max_results)

if __name__ == "__main__":
    main()
