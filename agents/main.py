"""
Gmail CRM Agent - Main Entry Point

This module implements the main pipeline for processing Gmail threads,
classifying them as leads or spam, extracting contact information,
and updating Google Sheets CRM.
"""

import sys
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .config import load_config
from .gmail_client import GmailClient
from .sheets_client import SheetsClient
from .llm import LLMProcessor
from .state_store import StateStore
from .spam_filter import SpamFilter

# Initialize rich console for output
console = Console()


def setup_logging(debug: bool = False) -> None:
    """
    Setup logging configuration.

    Args:
        debug: Enable debug logging
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("gmail_crm_agent.log"),
            logging.StreamHandler() if debug else logging.NullHandler(),
        ],
    )


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Gmail CRM Agent - Automatic lead processing from Gmail to Google Sheets"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without writing to Google Sheets (for testing)",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Process emails from the last N days (modifies Gmail query)",
    )

    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Maximum number of threads to process",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show processing statistics and exit",
    )

    parser.add_argument(
        "--clear-state",
        action="store_true",
        help="Clear processed state (WARNING: will reprocess all emails)",
    )

    return parser.parse_args()


def build_gmail_query(base_query: str, days: int = None) -> str:
    """
    Build Gmail query with optional date filter.

    Args:
        base_query: Base query from config
        days: Number of days to look back

    Returns:
        Final Gmail query string
    """
    if days:
        date_str = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
        return f"{base_query} after:{date_str}"
    return base_query


def process_thread(
    gmail_client: GmailClient,
    sheets_client: SheetsClient,
    llm_processor: LLMProcessor,
    spam_filter: SpamFilter,
    state_store: StateStore,
    thread_id: str,
    labels: Dict[str, str],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Process a single Gmail thread through the full pipeline.

    Pipeline:
    1. Fetch thread data from Gmail
    2. Extract headers and convert to text
    3. Check spam filter (denylist) BEFORE LLM
    4. If passes spam filter, classify with LLM
    5. If lead: extract contact info, generate summary, upsert to Sheets
    6. Apply Gmail labels
    7. Mark as processed in state store

    Args:
        gmail_client: Gmail API client
        sheets_client: Google Sheets API client
        llm_processor: LLM processor
        spam_filter: Spam filter instance
        state_store: State store for tracking processed threads
        thread_id: Gmail thread ID
        labels: Gmail label IDs mapping
        dry_run: If True, don't write to Sheets or apply labels

    Returns:
        Dictionary with processing result
    """
    logger = logging.getLogger(__name__)

    try:
        # 1. Fetch thread data
        thread = gmail_client.fetch_thread(thread_id)
        if not thread:
            state_store.mark_processed(thread_id, reason="error", metadata={"error": "fetch_failed"})
            return {"status": "error", "reason": "Failed to fetch thread"}

        # 2. Convert to text and extract headers
        thread_text, headers = gmail_client.thread_to_text_and_headers(thread)
        subject = headers.get("Subject", "")
        from_header = headers.get("From", "")

        # Extract sender email for logging
        import re
        from_email_match = re.search(r"<([^>]+)>", from_header) or re.search(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", from_header
        )
        from_email = from_email_match.group(1 if from_email_match and "<" in from_header else 0) if from_email_match else from_header

        logger.info(f"Processing thread {thread_id} from {from_email}: {subject[:50]}...")

        # 3. Check spam filter FIRST (before LLM)
        spam_result = spam_filter.is_spam(from_email, headers, subject, thread_text)

        if spam_result.is_spam:
            # Denylist match - skip without LLM call
            logger.info(f"  → SPAM (denylist): {spam_result.reason} | Rule: {spam_result.matched_rule}")

            if not dry_run:
                gmail_client.add_label_to_thread(thread_id, labels["ai_skip"])

            state_store.mark_processed(
                thread_id,
                reason="spam",
                metadata={
                    "sender": from_email,
                    "subject": subject[:100],
                    "spam_reason": spam_result.reason,
                    "matched_rule": spam_result.matched_rule,
                },
            )

            return {
                "status": "spam",
                "reason": spam_result.reason,
                "sender": from_email,
                "action": "skipped",
                "label": "ai_skip",
            }

        # 4. Classify with LLM
        logger.debug("  → Passed denylist, classifying with LLM...")
        classification = llm_processor.classify_thread(thread_text)

        if not classification["is_lead"]:
            # LLM classified as not a lead
            logger.info(f"  → SKIP (LLM): {classification['reason']}")

            if not dry_run:
                gmail_client.add_label_to_thread(thread_id, labels["ai_skip"])

            state_store.mark_processed(
                thread_id,
                reason="skip",
                metadata={
                    "sender": from_email,
                    "subject": subject[:100],
                    "llm_reason": classification["reason"],
                    "confidence": classification.get("confidence", "unknown"),
                },
            )

            return {
                "status": "skip",
                "reason": classification["reason"],
                "sender": from_email,
                "action": "skipped",
                "label": "ai_skip",
            }

        # 5. Extract contact information
        logger.debug("  → LEAD detected, extracting contact info...")
        contact_info = llm_processor.extract_contact(thread_text, headers)

        # 6. Generate summary
        summary = llm_processor.summarize_thread(thread_text)

        # 7. Prepare lead data for Sheets
        lead_data = {
            "company": contact_info.get("company", ""),
            "address": contact_info.get("address", ""),
            "website": contact_info.get("website", ""),
            "lpr_name": contact_info.get("lpr_name", ""),
            "lpr_phone": contact_info.get("lpr_phone", ""),
            "lpr_email": contact_info.get("lpr_email", from_email),  # Fallback to from_email
            "notes": summary.get("notes", ""),
            "source": "Gmail",
            "thread_id": thread_id,
            "status": "New",
        }

        # 8. Upsert to Google Sheets
        if dry_run:
            logger.info(f"  → LEAD: {lead_data['lpr_email']} | [DRY RUN - not writing to Sheets]")
            action = "dry_run"
        else:
            row_idx = sheets_client.upsert_lead(lead_data)
            action = "updated" if row_idx > 0 else "inserted"
            logger.info(f"  → LEAD: {lead_data['lpr_email']} | Action: {action}")

            # Apply lead label
            gmail_client.add_label_to_thread(thread_id, labels["ai_lead"])

        # 9. Mark as processed
        state_store.mark_processed(
            thread_id,
            reason="lead",
            metadata={
                "sender": from_email,
                "subject": subject[:100],
                "lpr_email": lead_data["lpr_email"],
                "action": action,
                "confidence": classification.get("confidence", "unknown"),
            },
        )

        return {
            "status": "lead",
            "sender": from_email,
            "action": action,
            "label": "ai_lead",
            "data": lead_data,
        }

    except Exception as e:
        logger.error(f"Error processing thread {thread_id}: {e}", exc_info=True)

        if not dry_run:
            try:
                gmail_client.add_label_to_thread(thread_id, labels.get("ai_error"))
            except:
                pass

        state_store.mark_processed(
            thread_id,
            reason="error",
            metadata={"error": str(e)},
        )

        return {
            "status": "error",
            "reason": str(e),
            "sender": "unknown",
            "action": "error",
            "label": "ai_error",
        }


def main():
    """Main entry point for the Gmail CRM Agent."""
    args = parse_args()

    # Setup logging
    setup_logging(debug=args.debug)
    logger = logging.getLogger(__name__)

    console.print("[bold blue]Gmail CRM Agent[/bold blue]")
    console.print("=" * 70)

    try:
        # Load configuration
        config = load_config()
        if args.debug:
            console.print("\n[yellow]Configuration:[/yellow]")
            config.print_config()

        # Handle --status command
        if args.status:
            state_store = StateStore(config.processed_store_path)
            summary = state_store.get_processing_summary()

            table = Table(title="Gmail CRM Agent Status")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")

            table.add_row("Total Processed", str(summary["total_processed"]))
            table.add_row("Leads Found", str(summary["leads_found"]))
            table.add_row("Skipped/Spam", str(summary["skipped"]))
            table.add_row("Errors", str(summary["errors"]))
            table.add_row("Success Rate", f"{summary['success_rate']}%")
            table.add_row("Last Run", summary["last_run"] or "Never")

            console.print(table)
            return

        # Handle --clear-state command
        if args.clear_state:
            state_store = StateStore(config.processed_store_path)
            state_store.clear_processed()
            console.print("[green]✓ State cleared. All threads will be reprocessed.[/green]")
            return

        # Initialize components
        console.print("[yellow]Initializing components...[/yellow]")

        gmail_client = GmailClient(config.gmail_user, str(config.gmail_token_path))
        sheets_client = SheetsClient(config.sheets_id, config.sheets_tab)
        llm_processor = LLMProcessor()
        spam_filter = SpamFilter(config.spam_rules_path)
        state_store = StateStore(config.processed_store_path)

        console.print(f"[green]✓ Using LLM provider: {config.model_provider}[/green]")
        console.print(f"[green]✓ Spam rules loaded from: {config.spam_rules_path}[/green]")
        console.print(f"[green]✓ State store: {config.processed_store_path}[/green]")

        if args.dry_run:
            console.print("[yellow]⚠ DRY RUN MODE - No writes to Sheets or Gmail labels[/yellow]")

        # Validate Sheets access
        if not args.dry_run:
            console.print("[yellow]Validating Google Sheets access...[/yellow]")
            if not sheets_client.validate_access():
                console.print("[red]Error: Cannot access Google Sheets. Check credentials.[/red]")
                sys.exit(1)
            console.print("[green]✓ Google Sheets access validated[/green]")

        # Create/ensure labels exist
        labels = gmail_client.ensure_labels(["ai_lead", "ai_skip", "ai_error"])
        console.print(f"[green]✓ Gmail labels ready[/green]")

        # Build Gmail query
        gmail_query = build_gmail_query(config.gmail_query, args.days)
        max_results = args.max or config.max_threads

        console.print(f"\n[yellow]Searching Gmail with query:[/yellow] {gmail_query}")
        console.print(f"[yellow]Max results:[/yellow] {max_results}")

        # Search for threads
        thread_ids = gmail_client.search_threads(gmail_query, max_results=max_results)

        # Filter out already processed threads
        unprocessed_threads = [tid for tid in thread_ids if not state_store.is_processed(tid)]

        console.print(
            f"\n[blue]Found {len(thread_ids)} threads, "
            f"{len(unprocessed_threads)} unprocessed[/blue]"
        )

        if not unprocessed_threads:
            console.print("[yellow]No new threads to process[/yellow]")
            return

        # Process threads
        stats = {"processed": 0, "leads": 0, "spam": 0, "skipped": 0, "errors": 0}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Processing threads...", total=len(unprocessed_threads)
            )

            for thread_id in unprocessed_threads:
                result = process_thread(
                    gmail_client,
                    sheets_client,
                    llm_processor,
                    spam_filter,
                    state_store,
                    thread_id,
                    labels,
                    dry_run=args.dry_run,
                )

                stats["processed"] += 1
                if result["status"] == "lead":
                    stats["leads"] += 1
                elif result["status"] == "spam":
                    stats["spam"] += 1
                elif result["status"] == "skip":
                    stats["skipped"] += 1
                elif result["status"] == "error":
                    stats["errors"] += 1

                progress.advance(task)

        # Display results
        console.print("\n[bold green]Processing Complete![/bold green]")

        table = Table(title="Processing Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="magenta")

        table.add_row("Total Processed", str(stats["processed"]))
        table.add_row("Leads Found", str(stats["leads"]))
        table.add_row("Spam (Denylist)", str(stats["spam"]))
        table.add_row("Skipped (LLM)", str(stats["skipped"]))
        table.add_row("Errors", str(stats["errors"]))

        console.print(table)

        if stats["leads"] == 0 and stats["processed"] > 0:
            console.print(
                "\n[yellow]ℹ No leads found. Check spam rules if this seems incorrect.[/yellow]"
            )

    except KeyboardInterrupt:
        console.print("\n[yellow]Process interrupted by user[/yellow]")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        console.print(f"\n[red]Fatal error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
